import os
from app.rag.loaders import get_loader_for_file
from app.db.session import SessionLocal
from app.db.models import KnowledgeSource
from app.services.knowledge_service import process_knowledge_source
# trigger reload for docx2txt

def ingest_document(file_path: str, filename: str, persona_id: str) -> str:
    db = SessionLocal()
    # Create DB Record immediately
    source = KnowledgeSource(
        persona_id=persona_id,
        name=filename,
        source_type="UPLOAD",
        original_filename=filename,
        status="PROCESSING"
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    source_id = source.id
    db.close()
    
    try:
        # Extract Text
        loader = get_loader_for_file(file_path)
        documents = loader.load()
        full_text = "\n".join([doc.page_content for doc in documents])
        
        # Pass to unified pipeline
        process_knowledge_source(
            source_id=source_id,
            text_content=full_text,
            metadata={"original_filename": filename}
        )
    except Exception as e:
        db = SessionLocal()
        source = db.query(KnowledgeSource).filter(KnowledgeSource.id == source_id).first()
        if source:
            source.status = "FAILED"
            source.error_message = str(e)
            db.commit()
        db.close()
        
    return source_id
