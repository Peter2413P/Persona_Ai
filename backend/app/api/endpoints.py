from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
import os
import shutil

from app.services.document_service import ingest_document
from app.services.knowledge_service import get_all_knowledge_sources, get_knowledge_source_status, delete_knowledge_source
from app.services.research_service import ingest_url_background
from app.db.session import SessionLocal
from app.db.models import KnowledgeSource, Persona

router = APIRouter()

from app.rag.database import get_vector_store
@router.get("/debug-chroma/{persona_id}")
def debug_chroma(persona_id: str):
    vs = get_vector_store()
    collection = vs._collection
    
    results = collection.get(where={"persona_id": persona_id})
    metadatas = results.get("metadatas", [])
    documents = results.get("documents", [])
    
    filmography_records = [m for m in metadatas if m and m.get("content_type") == "filmography_record"]
    
    sample = []
    if filmography_records:
        sample = filmography_records[:5]
        
    all_content_types = list(set([m.get("content_type", "NONE") for m in metadatas if m]))
        
    return {
        "total_chunks": len(metadatas),
        "total_filmography_records": len(filmography_records),
        "content_types_found": all_content_types,
        "sample_filmography": sample,
        "first_doc": documents[0] if documents else None
    }

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    persona_id: str
    message: str
    history: List[ChatMessage] = []

class SourceItem(BaseModel):
    type: str  # "document" or "internet"
    title: str
    content: str
    url: Optional[str] = None

class ChatResponse(BaseModel):
    answer: str
    sources: List[SourceItem]

class DocumentResponse(BaseModel):
    id: str
    name: str
    source_type: str
    status: str
    chunk_count: int
    created_at: str

class UrlRequest(BaseModel):
    url: str
    persona_id: str

class PersonaCreate(BaseModel):
    name: str

class PersonaResponse(BaseModel):
    id: str
    name: str
    created_at: str

@router.post("/personas", response_model=PersonaResponse)
def create_persona(request: PersonaCreate):
    db = SessionLocal()
    persona = Persona(name=request.name)
    db.add(persona)
    db.commit()
    db.refresh(persona)
    resp = {"id": persona.id, "name": persona.name, "created_at": persona.created_at.isoformat()}
    db.close()
    return resp

@router.get("/personas", response_model=List[PersonaResponse])
def get_personas():
    db = SessionLocal()
    personas = db.query(Persona).order_by(Persona.created_at.desc()).all()
    resp = [{"id": p.id, "name": p.name, "created_at": p.created_at.isoformat()} for p in personas]
    db.close()
    return resp

@router.delete("/personas/{persona_id}")
def delete_persona(persona_id: str):
    db = SessionLocal()
    persona = db.query(Persona).filter(Persona.id == persona_id).first()
    if not persona:
        db.close()
        raise HTTPException(status_code=404, detail="Persona not found")
    
    # Cascade delete will handle knowledge sources in DB, but we need to purge ChromaDB
    from app.rag.database import get_vector_store
    vector_store = get_vector_store()
    try:
        vector_store._collection.delete(where={"persona_id": persona_id})
    except Exception:
        pass # If collection is empty or doesn't exist yet
        
    db.delete(persona)
    db.commit()
    db.close()
    return {"status": "success"}

@router.get("/health")
def health_check():
    return {"status": "ok"}

@router.post("/upload")
async def upload_document(persona_id: str, file: UploadFile = File(...)):
    db = SessionLocal()
    persona = db.query(Persona).filter(Persona.id == persona_id).first()
    db.close()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
        
    try:
        os.makedirs("temp_uploads", exist_ok=True)
        file_path = f"temp_uploads/{file.filename}"
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        doc_id = ingest_document(file_path, file.filename, persona_id)
        
        if os.path.exists(file_path):
            os.remove(file_path)
            
        return {"status": "success", "id": doc_id, "filename": file.filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.post("/knowledge/url")
async def ingest_url(request: UrlRequest, background_tasks: BackgroundTasks):
    if not request.url.startswith("http://") and not request.url.startswith("https://"):
        raise HTTPException(status_code=400, detail="Invalid URL format. Must start with http:// or https://")
        
    db = SessionLocal()
    persona = db.query(Persona).filter(Persona.id == request.persona_id).first()
    if not persona:
        db.close()
        raise HTTPException(status_code=404, detail="Persona not found")
        
    source_type = "WIKIPEDIA" if "wikipedia.org" in request.url else "WEBSITE"
    source = KnowledgeSource(
        persona_id=request.persona_id,
        name=request.url,
        source_type=source_type,
        source_url=request.url,
        status="PROCESSING"
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    source_id = source.id
    db.close()
    
    background_tasks.add_task(ingest_url_background, source_id, request.url)
    return {"status": "success", "id": source_id}

from fastapi.responses import StreamingResponse
from app.services.chat_service import stream_chat_response

@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    try:
        history_dicts = [{"role": msg.role, "content": msg.content} for msg in request.history]
        return StreamingResponse(
            stream_chat_response(request.persona_id, request.message, history_dicts),
            media_type="text/event-stream"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class TTSRequest(BaseModel):
    text: str
    persona_id: Optional[str] = None

import io
from fastapi.responses import Response

@router.post("/chat/tts")
async def generate_tts(request: TTSRequest):
    try:
        from app.services.tts_service import get_tts_provider, clean_text_for_tts
        from app.services.voice_service import generate_persona_speech, generate_persona_speech_async, get_voice_profile
        
        # Clean text for TTS
        cleaned_text = clean_text_for_tts(request.text)
        
        # Check if persona has custom voice profile ready
        if request.persona_id:
            try:
                profile = get_voice_profile(request.persona_id)
                if profile and profile.get("status") == "READY":
                    audio_bytes = await generate_persona_speech_async(request.persona_id, cleaned_text)
                    media_type = "audio/wav" if audio_bytes.startswith(b"RIFF") else "audio/mpeg"
                    headers = {"X-Voice-Conditioned": "true", "X-Voice-Persona": str(request.persona_id), "X-Voice-Provider": str(profile.get("active_provider") or profile.get("provider") or "local")}
                    return Response(content=audio_bytes, media_type=media_type, headers=headers)
            except Exception as e:
                fallback_enabled = os.getenv("VOICE_PROVIDER_FALLBACK_ENABLED", "false").lower() == "true"
                if not fallback_enabled:
                    raise HTTPException(status_code=500, detail=f"Voice generation failed: {str(e)}")
                print(f"[VOICE CLONING] Fallback to default TTS due to error: {e}")
                pass
                
        provider = get_tts_provider()
        audio_bytes = await provider.synthesize(cleaned_text)
        from app.services.audio_processing_service import normalize_loudness
        audio_bytes = normalize_loudness(audio_bytes, target_rms_db=-14.0)
        media_type = "audio/wav" if audio_bytes.startswith(b"RIFF") else "audio/mpeg"
        return Response(content=audio_bytes, media_type=media_type, headers={"X-Voice-Conditioned": "false", "X-Voice-Provider": "default"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/documents", response_model=List[DocumentResponse])
async def list_documents(persona_id: str):
    try:
        docs = get_all_knowledge_sources(persona_id)
        return docs
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/knowledge/{source_id}/status")
async def get_knowledge_status(source_id: str):
    status = get_knowledge_source_status(source_id)
    if not status:
        raise HTTPException(status_code=404, detail="Source not found")
    return status

@router.delete("/documents/{doc_id}")
async def remove_document(doc_id: str):
    try:
        delete_knowledge_source(doc_id)
        return {"status": "success", "id": doc_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Voice Identity / Voice Cloning Endpoints ---

@router.post("/personas/{persona_id}/voice/samples")
async def upload_persona_voice_sample(persona_id: str, file: UploadFile = File(...)):
    try:
        from app.services.voice_service import upload_voice_sample
        content = await file.read()
        res = upload_voice_sample(persona_id, content, file.filename)
        return res
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/personas/{persona_id}/voice/samples")
async def list_persona_voice_samples(persona_id: str):
    try:
        from app.services.voice_service import get_voice_samples
        return get_voice_samples(persona_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/personas/{persona_id}/voice/samples/{sample_id}")
async def remove_persona_voice_sample(persona_id: str, sample_id: str):
    try:
        from app.services.voice_service import delete_voice_sample
        success = delete_voice_sample(persona_id, sample_id)
        if not success:
            raise HTTPException(status_code=404, detail="Sample not found")
        return {"status": "success", "id": sample_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/personas/{persona_id}/voice/create")
async def create_persona_voice(persona_id: str):
    try:
        from app.services.voice_service import create_voice_profile
        res = create_voice_profile(persona_id)
        return res
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/personas/{persona_id}/voice")
async def get_persona_voice_status(persona_id: str):
    try:
        from app.services.voice_service import get_voice_profile
        return get_voice_profile(persona_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/personas/{persona_id}/voice")
async def remove_persona_voice_profile(persona_id: str):
    try:
        from app.services.voice_service import delete_voice_profile
        delete_voice_profile(persona_id)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class VoiceProviderToggleRequest(BaseModel):
    provider: str

@router.put("/personas/{persona_id}/voice/provider")
async def toggle_persona_voice_provider(persona_id: str, request: VoiceProviderToggleRequest):
    try:
        from app.services.voice_service import set_voice_provider
        return set_voice_provider(persona_id, request.provider)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/voice/f5tts/status")
async def get_f5tts_status():
    try:
        from app.services.providers.f5tts_provider import F5TTSVoiceProvider
        p = F5TTSVoiceProvider()
        is_valid, msg = p.validate_configuration()
        if is_valid:
            return {"status": "online", "message": msg, "url": p.base_url, "model": "F5-TTS_v1"}
        else:
            return {"status": "offline", "message": msg, "url": p.base_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check F5-TTS status: {str(e)}")

class VoiceTestRequest(BaseModel):
    text: Optional[str] = "Hello, I am your AI persona. This is a test of my synthesized voice."
    provider: Optional[str] = None

@router.post("/personas/{persona_id}/voice/test")
async def test_persona_voice(persona_id: str, request: VoiceTestRequest):
    try:
        from app.services.voice_service import test_voice, set_voice_provider, get_voice_profile
        if request.provider:
            set_voice_provider(persona_id, request.provider)
        audio_bytes = test_voice(persona_id, request.text or "")
        media_type = "audio/wav" if audio_bytes.startswith(b"RIFF") else "audio/mpeg"
        prof = get_voice_profile(persona_id) or {}
        active_prov = str(request.provider or prof.get("active_provider") or prof.get("provider") or "local")
        headers = {"X-Voice-Conditioned": "true", "X-Voice-Persona": str(persona_id), "X-Voice-Provider": active_prov}
        return Response(content=audio_bytes, media_type=media_type, headers=headers)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class F5TTSSettings(BaseModel):
    reference_text: str
    randomize_seed: bool
    seed: int
    speed: float
    nfe_steps: int
    cross_fade_duration: float

@router.put("/personas/{persona_id}/voice/f5tts-settings")
async def update_f5tts_settings(persona_id: str, settings: F5TTSSettings):
    try:
        from app.db.session import SessionLocal
        from app.db.models import VoiceProfile
        db = SessionLocal()
        try:
            profile = db.query(VoiceProfile).filter(VoiceProfile.persona_id == persona_id).first()
            if not profile:
                raise ValueError("Voice profile not found.")
            meta = dict(profile.provider_metadata or {})
            meta["f5tts_settings"] = settings.dict()
            profile.provider_metadata = meta
            db.commit()
            return {"success": True}
        finally:
            db.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/personas/{persona_id}/voice/diagnostic")
async def get_persona_voice_diagnostic_report(persona_id: str):
    try:
        from app.services.voice_service import get_persona_voice_diagnostic
        return get_persona_voice_diagnostic(persona_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/personas/{persona_id}/voice/evaluate")
async def evaluate_persona_voice_cloning(persona_id: str):
    try:
        from app.services.voice_service import evaluate_persona_voice
        return evaluate_persona_voice(persona_id)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/personas/{persona_id}/voice/eval_audio/{sentence_index}")
async def get_persona_eval_audio_file(persona_id: str, sentence_index: int):
    try:
        from app.services.voice_service import get_eval_audio
        audio_bytes = get_eval_audio(persona_id, sentence_index)
        return Response(content=audio_bytes, media_type="audio/wav")
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
