import os
import io
import json
import shutil
import wave
import uuid
import numpy as np
from datetime import datetime
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any

from app.db.session import SessionLocal
from app.db.models import Persona, VoiceProfile, VoiceSample

# Storage base path
STORAGE_BASE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "storage", "personas")

def get_persona_voice_dir(persona_id: str) -> str:
    path = os.path.join(STORAGE_BASE_PATH, persona_id, "voice")
    os.makedirs(path, exist_ok=True)
    return path

# --- Audio Validation & Normalization ---

def validate_and_normalize_audio(file_path: str, filename: str) -> Dict[str, Any]:
    """
    Validates audio duration, sample rate, channels, and checks for silence using audio_processing_service.
    Returns metadata dict if valid, or raises ValueError with user-friendly error message.
    """
    ext = os.path.splitext(filename)[1].lower()
    allowed_exts = [".wav", ".mp3", ".m4a", ".ogg", ".flac"]
    if ext not in allowed_exts:
        raise ValueError(f"Unsupported audio format '{ext}'. Supported formats are: WAV, MP3, M4A, OGG, FLAC.")
    
    file_size = os.path.getsize(file_path)
    if file_size == 0:
        raise ValueError("Audio file is empty.")
    if file_size > 20 * 1024 * 1024:
        raise ValueError("Audio file size exceeds the 20MB limit.")

    from app.services.audio_processing_service import preprocess_reference_audio
    try:
        # Preprocess and normalize audio to mono PCM WAV
        ref_path = os.path.join(os.path.dirname(file_path), "reference.wav")
        meta = preprocess_reference_audio(file_path, ref_path, target_sr=16000)
        
        meta["file_path"] = ref_path
        meta["file_size"] = os.path.getsize(ref_path)
        return meta
    except Exception as e:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
        raise e

# --- Voice Provider Abstraction ---
from app.services.providers.base import VoiceProvider
from app.services.providers.f5tts_provider import F5TTSVoiceProvider


class LocalVoiceProvider(VoiceProvider):
    """
    Local voice cloning provider.
    Attempts Coqui TTS (XTTS-v2), then HuggingFace SpeechT5 conditioned on 512-dim speaker embedding,
    and finally falls back to local TTS with loudness normalization and subtle formant-preserving pitch adaptation.
    """
    def create_profile(self, persona_id: str, sample_paths: List[str], voice_profile: VoiceProfile) -> str:
        if not sample_paths:
            raise ValueError("No audio samples provided for voice cloning.")
        
        valid_paths = [p for p in sample_paths if os.path.exists(p)]
        if not valid_paths:
            raise ValueError("Audio sample files could not be found on disk.")

        total_size = sum(os.path.getsize(p) for p in valid_paths)
        if total_size < 1000:
            raise ValueError("Audio sample is too short. Please upload at least 10 seconds.")

        return f"local_clone_{persona_id}"

    def generate_speech(self, text: str, voice_profile: VoiceProfile) -> bytes:
        from app.services.audio_processing_service import (
            normalize_loudness,
            apply_subtle_pitch_correction,
            analyze_vocal_identity
        )
        sample_paths = voice_profile.reference_audio_files or []
        valid_paths = [p for p in sample_paths if os.path.exists(p)]
        
        voice_dir = get_persona_voice_dir(voice_profile.persona_id)
        profile_json_path = os.path.join(voice_dir, "speaker_profile.json")
        ref_profile = None
        if os.path.exists(profile_json_path):
            try:
                with open(profile_json_path, "r", encoding="utf-8") as f:
                    ref_profile = json.load(f)
            except Exception:
                pass

        # Section 7: Voice Generation API Structured Logging
        print(f"[VOICE] Profile: {voice_profile.persona_id}")
        print(f"[VOICE] Reference audio: {'loaded' if ref_profile else 'not found'}")
        ref_dur = 0.0
        if ref_profile:
            ref_dur = ref_profile.get("duration", 0.0) or ref_profile.get("analytical_features", {}).get("duration", 0.0)
        print(f"[VOICE] Reference duration: {ref_dur} seconds")
        print(f"[VOICE] Language: en")
        print(f"[VOICE] Generation started")

        audio_bytes = None
        default_voice_fallback_used = False
        model_name_used = "Unknown"

        # Attempt 1: Coqui TTS (XTTS-v2) or F5-TTS if installed in environment (Zero-shot reference WAV cloning)
        if not audio_bytes and valid_paths:
            try:
                from TTS.api import TTS
                model_name = os.getenv("VOICE_MODEL", "tts_models/multilingual/multi-dataset/xtts_v2")
                tts = TTS(model_name)
                output_file = os.path.join(voice_dir, f"temp_xtts_{uuid.uuid4().hex[:6]}.wav")
                tts.tts_to_file(text=text, speaker_wav=valid_paths, language="en", file_path=output_file)
                with open(output_file, "rb") as f:
                    audio_bytes = f.read()
                if os.path.exists(output_file):
                    os.remove(output_file)
                if audio_bytes:
                    model_name_used = "Coqui XTTS-v2 (Zero-shot Reference Audio)"
                    print(f"[VOICE] Speaker conditioning: loaded (Reference WAV files)")
                    print(f"[VOICE] TTS model: {model_name_used}")
            except Exception:
                pass

        # Attempt 2: HuggingFace SpeechT5 conditioned on official SpeechBrain VoxCeleb x-vector
        if not audio_bytes and ref_profile:
            speaker_embedding = None
            if "voice_cloning_conditioning" in ref_profile and "speaker_embedding" in ref_profile["voice_cloning_conditioning"]:
                speaker_embedding = ref_profile["voice_cloning_conditioning"]["speaker_embedding"]
            elif "speaker_embedding" in ref_profile:
                speaker_embedding = ref_profile["speaker_embedding"]

            # Only use SpeechT5 if speaker embedding is valid (512 dims and not all zeros)
            if speaker_embedding and len(speaker_embedding) == 512 and any(abs(x) > 1e-6 for x in speaker_embedding):
                try:
                    import torch
                    from transformers import SpeechT5ForTextToSpeech, SpeechT5Processor, SpeechT5HifiGan
                    
                    # Remove hardcoded local_files_only=True to prevent LocalEntryNotFoundError when cache is empty
                    try:
                        processor = SpeechT5Processor.from_pretrained("microsoft/speecht5_tts", local_files_only=True)
                        model = SpeechT5ForTextToSpeech.from_pretrained("microsoft/speecht5_tts", local_files_only=True)
                        vocoder = SpeechT5HifiGan.from_pretrained("microsoft/speecht5_hifigan", local_files_only=True)
                    except Exception:
                        processor = SpeechT5Processor.from_pretrained("microsoft/speecht5_tts")
                        model = SpeechT5ForTextToSpeech.from_pretrained("microsoft/speecht5_tts")
                        vocoder = SpeechT5HifiGan.from_pretrained("microsoft/speecht5_hifigan")
                    
                    inputs = processor(text=text, return_tensors="pt")
                    speaker_embeddings = torch.tensor([speaker_embedding], dtype=torch.float32)
                    
                    with torch.no_grad():
                        speech = model.generate_speech(inputs["input_ids"], speaker_embeddings, vocoder=vocoder)
                    
                    speech_arr = speech.numpy()
                    out_fp = io.BytesIO()
                    import soundfile as sf
                    sf.write(out_fp, speech_arr, 16000, format='WAV', subtype='PCM_16')
                    out_fp.seek(0)
                    audio_bytes = out_fp.read()
                    if audio_bytes:
                        model_name_used = "Microsoft SpeechT5 (Conditioned on SpeechBrain VoxCeleb x-vector)"
                        print(f"[VOICE] Speaker conditioning: loaded (SpeechBrain VoxCeleb x-vector)")
                        print(f"[VOICE] TTS model: {model_name_used}")
                except Exception as e:
                    print(f"[VOICE CLONING] SpeechT5 synthesis failed: {e}")
                    pass

        # Attempt 3: Fallback Local TTS with acoustic vocal conditioning
        if not audio_bytes:
            default_voice_fallback_used = True
            model_name_used = "Google gTTS (Default Unconditioned Fallback)"
            print(f"[VOICE] Speaker conditioning: fallback (Default unconditioned TTS)")
            print(f"[VOICE] TTS model: {model_name_used}")
            from gtts import gTTS
            tts = gTTS(text=text, lang='en', slow=False)
            fp = io.BytesIO()
            tts.write_to_fp(fp)
            fp.seek(0)
            audio_bytes = fp.read()

        # Phase 7: Loudness Normalization (-14 LUFS / RMS equivalent)
        audio_bytes = normalize_loudness(audio_bytes, target_rms_db=-14.0)

        # Section 5: Optional Subtle Pitch Correction (disabled by default, enabled=False)
        if ref_profile:
            audio_bytes = apply_subtle_pitch_correction(audio_bytes, ref_profile, max_shift_semitones=2.5, enabled=False)

        # Phase 4 & 12: Generate and save Developer Diagnostic Report
        try:
            diag_report = analyze_vocal_identity(ref_profile, audio_bytes, default_voice_used=default_voice_fallback_used)
            diag_path = os.path.join(voice_dir, "last_diagnostic.json")
            with open(diag_path, "w", encoding="utf-8") as f:
                json.dump(diag_report, f, indent=2)
        except Exception:
            pass

        print(f"[VOICE] Generation completed")
        return audio_bytes

    def delete_profile(self, voice_profile: VoiceProfile) -> bool:
        return True


class ElevenLabsProvider(VoiceProvider):
    """
    ElevenLabs voice cloning provider.
    Requires VOICE_API_KEY set in environment variables.
    """
    def create_profile(self, persona_id: str, sample_paths: List[str], voice_profile: VoiceProfile) -> str:
        import requests
        api_key = os.getenv("VOICE_API_KEY")
        if not api_key:
            raise ValueError("VOICE_API_KEY environment variable is not configured for ElevenLabs provider.")
        
        url = "https://api.elevenlabs.io/v1/voices/add"
        headers = {"xi-api-key": api_key}
        
        files = []
        for i, path in enumerate(sample_paths):
            if os.path.exists(path):
                files.append(("files", (os.path.basename(path), open(path, "rb"), "audio/mpeg")))
                
        data = {
            "name": f"Persona_{persona_id}_{uuid.uuid4().hex[:6]}",
            "description": "Cloned voice profile for PersonaForge AI"
        }
        
        try:
            response = requests.post(url, headers=headers, data=data, files=files, timeout=60)
            for _, f_obj, _ in files:
                f_obj.close()
            if response.status_code not in (200, 201):
                raise ValueError(f"ElevenLabs API error: {response.text}")
            res_json = response.json()
            return res_json.get("voice_id", f"elevenlabs_{persona_id}")
        except Exception as e:
            for _, f_obj, _ in files:
                f_obj.close()
            raise ValueError(f"Failed to create ElevenLabs voice profile: {str(e)}")

    def generate_speech(self, text: str, voice_profile: VoiceProfile) -> bytes:
        import requests
        from app.services.audio_processing_service import normalize_loudness, apply_subtle_pitch_correction, analyze_vocal_identity
        
        api_key = os.getenv("VOICE_API_KEY")
        if not api_key or not voice_profile.voice_id:
            raise ValueError("ElevenLabs voice profile is not properly configured.")
            
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_profile.voice_id}"
        headers = {
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg"
        }
        data = {
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
        }
        response = requests.post(url, headers=headers, json=data, timeout=60)
        if response.status_code == 200:
            audio_bytes = response.content
            # Apply loudness normalization and subtle pitch correction
            audio_bytes = normalize_loudness(audio_bytes, target_rms_db=-14.0)
            
            voice_dir = get_persona_voice_dir(voice_profile.persona_id)
            profile_json_path = os.path.join(voice_dir, "speaker_profile.json")
            ref_profile = None
            if os.path.exists(profile_json_path):
                try:
                    with open(profile_json_path, "r", encoding="utf-8") as f:
                        ref_profile = json.load(f)
                    audio_bytes = apply_subtle_pitch_correction(audio_bytes, ref_profile, max_shift_semitones=2.5)
                    diag_report = analyze_vocal_identity(ref_profile, audio_bytes, default_voice_used=False)
                    with open(os.path.join(voice_dir, "last_diagnostic.json"), "w", encoding="utf-8") as f_diag:
                        json.dump(diag_report, f_diag, indent=2)
                except Exception:
                    pass
            return audio_bytes
        raise ValueError(f"ElevenLabs speech generation error: {response.text}")

    def delete_profile(self, voice_profile: VoiceProfile) -> bool:
        import requests
        api_key = os.getenv("VOICE_API_KEY")
        if api_key and voice_profile.voice_id and not voice_profile.voice_id.startswith("local_"):
            url = f"https://api.elevenlabs.io/v1/voices/{voice_profile.voice_id}"
            headers = {"xi-api-key": api_key}
            try:
                requests.delete(url, headers=headers, timeout=10)
            except Exception:
                pass
        return True




def get_voice_provider(provider_name: Optional[str] = None) -> VoiceProvider:
    if not provider_name:
        provider_name = os.getenv("VOICE_PROVIDER", "f5tts").lower()
    else:
        provider_name = provider_name.lower()
    if provider_name == "f5tts":
        from app.services.providers.f5tts_provider import F5TTSVoiceProvider
        return F5TTSVoiceProvider()
    if provider_name == "elevenlabs":
        return ElevenLabsProvider()
    return LocalVoiceProvider()

# --- Core Service Functions ---

def upload_voice_sample(persona_id: str, file_bytes: bytes, filename: str) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        persona = db.query(Persona).filter(Persona.id == persona_id).first()
        if not persona:
            raise ValueError("Persona not found.")

        voice_dir = get_persona_voice_dir(persona_id)
        
        # Clear out old files as F5-TTS only uses one reference
        if os.path.exists(voice_dir):
            for f in os.listdir(voice_dir):
                if f.endswith('.wav') or f.endswith('.orig'):
                    try: os.remove(os.path.join(voice_dir, f))
                    except: pass
                    
        # Remove old VoiceSample records from DB
        db.query(VoiceSample).filter(VoiceSample.persona_id == persona_id).delete()

        original_path = os.path.join(voice_dir, "original.wav")

        with open(original_path, "wb") as f:
            f.write(file_bytes)

        # Validate and normalize using Phase 2 pipeline
        try:
            meta = validate_and_normalize_audio(original_path, filename)
        except Exception as e:
            if os.path.exists(original_path):
                os.remove(original_path)
            raise e

        sample = VoiceSample(
            persona_id=persona_id,
            filename=filename,
            file_path=meta["file_path"],
            duration=meta["duration"],
            sample_rate=meta["sample_rate"],
            file_size=meta["file_size"],
            status=meta["status"]
        )
        db.add(sample)
        
        # Update voice profile status if exists
        profile = db.query(VoiceProfile).filter(VoiceProfile.persona_id == persona_id).first()
        if not profile:
            profile = VoiceProfile(persona_id=persona_id, status="SAMPLES_UPLOADED")
            db.add(profile)
        else:
            if profile.status == "NOT_CONFIGURED":
                profile.status = "SAMPLES_UPLOADED"

        db.commit()
        db.refresh(sample)
        return {
            "id": sample.id,
            "filename": sample.filename,
            "duration": sample.duration,
            "file_size": sample.file_size,
            "status": sample.status,
            "warnings": meta.get("warnings", []),
            "created_at": sample.created_at.isoformat()
        }
    finally:
        db.close()


def get_voice_samples(persona_id: str) -> List[Dict[str, Any]]:
    db = SessionLocal()
    try:
        samples = db.query(VoiceSample).filter(VoiceSample.persona_id == persona_id).order_by(VoiceSample.created_at.desc()).all()
        return [{
            "id": s.id,
            "filename": s.filename,
            "duration": s.duration,
            "file_size": s.file_size,
            "status": s.status,
            "created_at": s.created_at.isoformat()
        } for s in samples]
    finally:
        db.close()


def delete_voice_sample(persona_id: str, sample_id: str) -> bool:
    db = SessionLocal()
    try:
        sample = db.query(VoiceSample).filter(VoiceSample.id == sample_id, VoiceSample.persona_id == persona_id).first()
        if not sample:
            return False

        if os.path.exists(sample.file_path):
            try:
                os.remove(sample.file_path)
            except Exception:
                pass

        db.delete(sample)
        
        remaining = db.query(VoiceSample).filter(VoiceSample.persona_id == persona_id).count()
        if remaining == 0:
            profile = db.query(VoiceProfile).filter(VoiceProfile.persona_id == persona_id).first()
            if profile and profile.status == "SAMPLES_UPLOADED":
                profile.status = "NOT_CONFIGURED"

        db.commit()
        return True
    finally:
        db.close()


def create_voice_profile(persona_id: str) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        persona = db.query(Persona).filter(Persona.id == persona_id).first()
        if not persona:
            raise ValueError("Persona not found.")

        samples = db.query(VoiceSample).filter(VoiceSample.persona_id == persona_id, VoiceSample.status == "READY").all()
        if not samples:
            raise ValueError("No valid audio samples found. Please upload at least one audio sample.")

        total_duration = sum(s.duration for s in samples)
        if total_duration < 5.0:
            raise ValueError(f"Audio sample is too short ({round(total_duration, 1)}s). Please upload at least 5 seconds of speech.")

        profile = db.query(VoiceProfile).filter(VoiceProfile.persona_id == persona_id).first()
        if not profile:
            profile = VoiceProfile(persona_id=persona_id)
            db.add(profile)

        profile.status = "PROCESSING"
        profile.error_message = None
        db.commit()

        sample_paths = [s.file_path for s in samples if os.path.exists(s.file_path)]
        voice_dir = get_persona_voice_dir(persona_id)

        # Phase 10: Create unified reference profile audio and extract acoustic profile + 512-dim embedding
        ref_profile_wav = os.path.join(voice_dir, "reference_profile.wav")
        try:
            import librosa
            import soundfile as sf
            combined_y = []
            for p in sample_paths:
                try:
                    y_s, _ = librosa.load(p, sr=16000, mono=True)
                    combined_y.extend(y_s)
                except Exception:
                    pass
            if combined_y:
                sf.write(ref_profile_wav, np.array(combined_y, dtype=np.float32), 16000, subtype='PCM_16')
                from app.services.audio_processing_service import extract_speaker_profile
                profile_data = extract_speaker_profile(ref_profile_wav)
                profile_json_path = os.path.join(voice_dir, "speaker_profile.json")
                with open(profile_json_path, "w", encoding="utf-8") as f_out:
                    json.dump(profile_data, f_out, indent=2)
        except Exception as e:
            # Continue even if profiling fails, so fallback remains operational
            pass

        active_prov = profile.active_provider or os.getenv("VOICE_PROVIDER", "f5tts")
        provider = get_voice_provider(active_prov)
        try:
            voice_id = provider.create_profile(persona_id, sample_paths, profile)
            profile.voice_id = voice_id
            profile.provider = active_prov
            profile.active_provider = active_prov
            profile.reference_audio_files = sample_paths
            profile.status = "READY"
            
            meta_dict = dict(profile.provider_metadata or {})
            
            # Initialize default F5-TTS advanced settings if not present
            if "f5tts_settings" not in meta_dict:
                meta_dict["f5tts_settings"] = {
                    "reference_text": "athula vanthu antha batsman vara ella ballayum six adika dhaan try pannuvaaru.",
                    "randomize_seed": False,
                    "seed": 259225565,
                    "speed": 0.9,
                    "nfe_steps": 20,
                    "cross_fade_duration": 0.11
                }
            
            profile.provider_metadata = meta_dict
            db.commit()

            # Run initial diagnostic baseline synthesis so diagnostic report is immediately ready
            try:
                test_voice(persona_id, "Hello, I am your AI persona. This is a baseline test of my voice.")
            except Exception:
                pass

            return {
                "success": True,
                "persona_id": persona_id,
                "voice_status": profile.status,
                "provider": profile.provider,
                "active_provider": profile.active_provider,
                "voice_id": profile.voice_id
            }
        except Exception as e:
            profile.status = "FAILED"
            profile.error_message = str(e)
            db.commit()
            raise ValueError(f"Voice profile creation failed: {str(e)}")
    finally:
        db.close()


def get_voice_profile(persona_id: str) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        profile = db.query(VoiceProfile).filter(VoiceProfile.persona_id == persona_id).first()
        samples_count = db.query(VoiceSample).filter(VoiceSample.persona_id == persona_id).count()
        
        voice_dir = get_persona_voice_dir(persona_id)
        profile_json_path = os.path.join(voice_dir, "speaker_profile.json")
        diag_path = os.path.join(voice_dir, "last_diagnostic.json")
        
        speaker_meta = {}
        if os.path.exists(profile_json_path):
            try:
                with open(profile_json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    speaker_meta = {
                        "analytical_features": data.get("analytical_features", {
                            "mean_f0": data.get("mean_f0"),
                            "median_f0": data.get("median_f0"),
                            "pitch_range": data.get("pitch_range"),
                            "loudness_lufs": data.get("lufs_est"),
                            "duration": data.get("duration"),
                            "sample_rate": data.get("sample_rate")
                        }),
                        "voice_cloning_conditioning": data.get("voice_cloning_conditioning", {
                            "reference_audio_uploaded": samples_count > 0,
                            "reference_audio_validated": True,
                            "speaker_representation_generated": True,
                            "tts_compatible_conditioning_created": "speaker_embedding" in data and len(data.get("speaker_embedding", [])) == 512,
                            "conditioning_type": data.get("conditioning_type", "READY_VOXCELEB_XVECTOR" if "speaker_embedding" in data else "UNKNOWN"),
                            "ready_for_synthesis": "speaker_embedding" in data and len(data.get("speaker_embedding", [])) == 512
                        }),
                        "mean_f0": data.get("mean_f0"),
                        "median_f0": data.get("median_f0"),
                        "pitch_range": data.get("pitch_range"),
                        "loudness_lufs": data.get("lufs_est"),
                        "has_embedding": "speaker_embedding" in data and len(data.get("speaker_embedding", [])) > 0,
                        "conditioning_type": data.get("conditioning_type", "UNKNOWN")
                    }
            except Exception:
                pass

        has_diagnostic = os.path.exists(diag_path)

        if not profile:
            return {
                "persona_id": persona_id,
                "status": "SAMPLES_UPLOADED" if samples_count > 0 else "NOT_CONFIGURED",
                "provider": "f5tts",
                "active_provider": "f5tts",
                "local_voice": {
                    "embedding_path": os.path.join(voice_dir, "speaker_profile.json") if os.path.exists(os.path.join(voice_dir, "speaker_profile.json")) else None,
                    "embedding_model": "SpeechBrain/spkrec-xvect-voxceleb",
                    "tts_model": "microsoft/speecht5_tts",
                    "verified": False,
                    "status": "not_configured"
                },
                "f5tts_voice": {
                    "model_name": "F5-TTS_v1",
                    "status": "not_configured",
                    "verified": False
                },
                "samples_count": samples_count,
                "error_message": None,
                "speaker_metadata": speaker_meta,
                "has_diagnostic": has_diagnostic
            }

        meta = profile.provider_metadata or {}
        local_voice = meta.get("local_voice", {
            "embedding_path": os.path.join(voice_dir, "speaker_profile.json") if os.path.exists(os.path.join(voice_dir, "speaker_profile.json")) else None,
            "embedding_model": "SpeechBrain/spkrec-xvect-voxceleb",
            "tts_model": "microsoft/speecht5_tts",
            "verified": profile.status == "READY" and (profile.provider == "local" or not profile.provider),
            "status": "ready" if os.path.exists(os.path.join(voice_dir, "speaker_profile.json")) else ("ready" if profile.status == "READY" and profile.provider == "local" else "not_configured")
        })
        f5tts_voice = meta.get("f5tts_voice", {
            "model_name": meta.get("model_name", "F5-TTS_v1") if profile.provider == "f5tts" else None,
            "status": "ready" if (profile.provider == "f5tts" and profile.status == "READY") else "not_configured",
            "verified": profile.provider == "f5tts" and profile.status == "READY"
        })

        return {
            "persona_id": persona_id,
            "status": profile.status,
            "provider": profile.provider or "local",
            "active_provider": profile.active_provider or profile.provider or os.getenv("VOICE_PROVIDER", "f5tts"),
            "local_voice": local_voice,
            "f5tts_voice": f5tts_voice,
            "voice_id": profile.voice_id,
            "samples_count": samples_count,
            "error_message": profile.error_message,
            "speaker_metadata": speaker_meta,
            "has_diagnostic": has_diagnostic
        }
    finally:
        db.close()


def delete_voice_profile(persona_id: str) -> bool:
    db = SessionLocal()
    try:
        profile = db.query(VoiceProfile).filter(VoiceProfile.persona_id == persona_id).first()
        if profile:
            provider = get_voice_provider()
            try:
                provider.delete_profile(profile)
            except Exception:
                pass
            db.delete(profile)
            db.commit()
            
        voice_dir = get_persona_voice_dir(persona_id)
        for fname in ["reference_profile.wav", "speaker_profile.json", "last_diagnostic.json"]:
            fpath = os.path.join(voice_dir, fname)
            if os.path.exists(fpath):
                try:
                    os.remove(fpath)
                except Exception:
                    pass
        return True
    finally:
        db.close()


def generate_persona_speech(persona_id: str, text: str) -> bytes:
    db = SessionLocal()
    try:
        profile = db.query(VoiceProfile).filter(VoiceProfile.persona_id == persona_id).first()
        if not profile or profile.status != "READY":
            raise ValueError("Voice profile is not ready for this persona.")
            
        active_prov = profile.active_provider or profile.provider or os.getenv("VOICE_PROVIDER", "f5tts")
        provider = get_voice_provider(active_prov)
        try:
            return provider.generate_speech(text, profile)
        except Exception as e:
            fallback_enabled = os.getenv("VOICE_PROVIDER_FALLBACK_ENABLED", "false").lower() == "true"
            if fallback_enabled and active_prov != "local":
                print(f"[VOICE] Provider {active_prov} generation failed ({str(e)}). Falling back to local provider.")
                local_prov = get_voice_provider("local")
                return local_prov.generate_speech(text, profile)
            raise e
    finally:
        db.close()


async def generate_persona_speech_async(persona_id: str, text: str, **kwargs) -> bytes:
    db = SessionLocal()
    try:
        profile = db.query(VoiceProfile).filter(VoiceProfile.persona_id == persona_id).first()
        if not profile or profile.status != "READY":
            raise ValueError("Voice profile is not ready for this persona.")
            
        active_prov = profile.active_provider or profile.provider or os.getenv("VOICE_PROVIDER", "f5tts")
        provider = get_voice_provider(active_prov)
        try:
            return await provider.generate_speech_async(text, profile, **kwargs)
        except Exception as e:
            fallback_enabled = os.getenv("VOICE_PROVIDER_FALLBACK_ENABLED", "false").lower() == "true"
            if fallback_enabled and active_prov != "local":
                print(f"[VOICE] Provider {active_prov} generation failed ({str(e)}). Falling back to local provider.")
                local_prov = get_voice_provider("local")
                return await local_prov.generate_speech_async(text, profile, **kwargs)
            raise e
    finally:
        db.close()


def set_voice_provider(persona_id: str, provider_name: str) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        profile = db.query(VoiceProfile).filter(VoiceProfile.persona_id == persona_id).first()
        if not profile:
            profile = VoiceProfile(
                persona_id=persona_id,
                status="NOT_CONFIGURED",
                provider=provider_name,
                active_provider=provider_name
            )
            db.add(profile)
        else:
            profile.active_provider = provider_name
            profile.provider = provider_name
        db.commit()
    finally:
        db.close()
    return get_voice_profile(persona_id)


def test_voice(persona_id: str, text: str) -> bytes:
    if not text or not text.strip():
        text = "Hello, I am your AI persona. This is a test of my synthesized voice."
    db = SessionLocal()
    try:
        profile = db.query(VoiceProfile).filter(VoiceProfile.persona_id == persona_id).first()
        if profile and profile.status == "READY":
            return generate_persona_speech(persona_id, text.strip())
            
        active_prov = (profile.active_provider if profile and profile.active_provider else None) or (profile.provider if profile and profile.provider else None) or os.getenv("VOICE_PROVIDER", "f5tts")
        provider = get_voice_provider(active_prov)
        if not profile:
            profile = VoiceProfile(persona_id=persona_id, status="READY", provider=active_prov, active_provider=active_prov)
        try:
            return provider.generate_speech(text.strip(), profile)
        except Exception as e:
            fallback_enabled = os.getenv("VOICE_PROVIDER_FALLBACK_ENABLED", "false").lower() == "true"
            if fallback_enabled and active_prov != "local":
                print(f"[VOICE TEST] Provider {active_prov} test failed ({str(e)}). Falling back to local provider.")
                local_prov = get_voice_provider("local")
                return local_prov.generate_speech(text.strip(), profile)
            raise e
    finally:
        db.close()


def get_persona_voice_diagnostic(persona_id: str) -> Dict[str, Any]:
    """
    Returns the latest developer diagnostic report for the persona's voice profile.
    If no diagnostic report exists yet but a profile exists, runs a test synthesis to generate one.
    """
    voice_dir = get_persona_voice_dir(persona_id)
    diag_path = os.path.join(voice_dir, "last_diagnostic.json")
    
    if not os.path.exists(diag_path):
        profile_json_path = os.path.join(voice_dir, "speaker_profile.json")
        if os.path.exists(profile_json_path):
            try:
                test_voice(persona_id, "Hello, I am your AI persona. This is a diagnostic evaluation test.")
            except Exception:
                pass

    if os.path.exists(diag_path):
        try:
            with open(diag_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    return {
        "status": "NOT_AVAILABLE",
        "message": "Diagnostic report is not yet available. Create a voice profile and run a test synthesis."
    }


def evaluate_persona_voice(persona_id: str) -> Dict[str, Any]:
    """
    Implements Phase 11 (Controlled Sentence Evaluation Test).
    Synthesizes speech across 8 standardized evaluation sentence types and returns comparative metrics and audio URLs.
    """
    test_sentences = [
        {"type": "Short sentence", "text": "Hello, nice to meet you."},
        {"type": "Long sentence", "text": "The development of artificial intelligence has transformed modern technology, enabling systems to understand natural language and generate realistic human speech with remarkable accuracy."},
        {"type": "Emotional sentence", "text": "I am absolutely thrilled and overjoyed to share this incredible news with everyone today!"},
        {"type": "Question", "text": "Could you please explain how the voice cloning algorithm preserves the fundamental pitch and acoustic timbre of the original speaker?"},
        {"type": "Statement", "text": "PersonaForge is a generic hybrid knowledge chatbot designed to answer complex questions using structured data and document ingestion."},
        {"type": "Sentence containing numbers", "text": "In 2026, the company reported a total revenue of 45,890,123 dollars across 127 different countries."},
        {"type": "Sentence containing names", "text": "Vijay, Rajinikanth, and Elon Musk were all featured in the latest comparative analysis report."},
        {"type": "Tamil/English mixed sentence", "text": "Vanakkam! Welcome to PersonaForge. Intha RAG chatbot rumba fast and accurate aaga answers generate pannum."}
    ]

    voice_dir = get_persona_voice_dir(persona_id)
    eval_dir = os.path.join(voice_dir, "eval_audio")
    os.makedirs(eval_dir, exist_ok=True)

    results = []
    for idx, item in enumerate(test_sentences):
        try:
            audio_bytes = generate_persona_speech(persona_id, item["text"])
            file_path = os.path.join(eval_dir, f"eval_{idx}.wav")
            with open(file_path, "wb") as f:
                f.write(audio_bytes)
            
            # Measure basic metrics of generated test clip
            duration = 0.0
            rms = 0.0
            lufs = -24.0
            mean_f0 = 0.0
            try:
                import soundfile as sf
                y, sr = sf.read(io.BytesIO(audio_bytes))
                if y.ndim > 1:
                    y = np.mean(y, axis=1)
                duration = round(float(len(y) / sr), 2)
                rms_val = float(np.sqrt(np.mean(y ** 2)))
                rms = round(rms_val, 4)
                lufs = round(float(20.0 * np.log10(max(rms_val, 1e-9))), 2)
                import librosa
                f0, _, _ = librosa.pyin(y, fmin=50, fmax=500, sr=sr)
                valid_f0 = f0[~np.isnan(f0)]
                if len(valid_f0) > 0:
                    mean_f0 = round(float(np.mean(valid_f0)), 2)
            except Exception:
                pass

            results.append({
                "index": idx,
                "type": item["type"],
                "text": item["text"],
                "status": "SUCCESS",
                "duration": duration,
                "rms_loudness": rms,
                "loudness_lufs": lufs,
                "mean_pitch_hz": mean_f0,
                "audio_url": f"/personas/{persona_id}/voice/eval_audio/{idx}"
            })
        except Exception as e:
            results.append({
                "index": idx,
                "type": item["type"],
                "text": item["text"],
                "status": "FAILED",
                "error": str(e)
            })

    return {
        "persona_id": persona_id,
        "evaluated_at": datetime.utcnow().isoformat(),
        "total_sentences": len(test_sentences),
        "results": results
    }


def get_eval_audio(persona_id: str, sentence_index: int) -> bytes:
    """
    Returns the generated audio bytes for a specific controlled evaluation sentence.
    """
    voice_dir = get_persona_voice_dir(persona_id)
    file_path = os.path.join(voice_dir, "eval_audio", f"eval_{sentence_index}.wav")
    if not os.path.exists(file_path):
        raise ValueError("Evaluation audio file not found. Please run the controlled evaluation first.")
    with open(file_path, "rb") as f:
        return f.read()
