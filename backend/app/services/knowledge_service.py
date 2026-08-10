from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.rag.database import get_vector_store
from app.db.session import SessionLocal
from app.db.models import KnowledgeSource, Entity, DatasetSchema, StructuredRecord, ExplicitFact
from sqlalchemy.orm import Session
from langchain_core.documents import Document
from app.services.extraction_service import detect_entity, detect_dataset_schema, normalize_table_records, extract_explicit_facts

def process_knowledge_source(source_id: str, text_content: str, metadata: dict, raw_records: list[dict] = None):
    db: Session = SessionLocal()
    source_record = db.query(KnowledgeSource).filter(KnowledgeSource.id == source_id).first()
    
    if not source_record:
        db.close()
        return

    try:
        source_title = metadata.get("source_title", source_record.name)
        
        # 1. Detect Entity
        entity_info = detect_entity(source_title, text_content)
        entity_name = entity_info["entity_name"]
        
        entity = db.query(Entity).filter(Entity.name == entity_name, Entity.persona_id == source_record.persona_id).first()
        if not entity:
            entity = Entity(persona_id=source_record.persona_id, name=entity_name, aliases=entity_info["aliases"])
            db.add(entity)
            db.commit()
            db.refresh(entity)
            
        source_record.entity_id = entity.id
        db.commit()

        docs = []
        dataset = None
        
        # 2. Process Structured Records
        if raw_records and len(raw_records) > 0:
            headers = list(raw_records[0].keys())
            schema_info = detect_dataset_schema(entity_name, headers, raw_records)
            
            dataset = DatasetSchema(
                entity_id=entity.id,
                dataset_type=schema_info["dataset_type"],
                primary_fields=schema_info["primary_fields"],
                attributes=schema_info["attributes"],
                sortable_fields=schema_info["sortable_fields"],
                filterable_fields=schema_info["filterable_fields"]
            )
            db.add(dataset)
            db.commit()
            db.refresh(dataset)
            
            normalized = normalize_table_records(dataset.dataset_type, raw_records)
            
            for idx, (raw_rec, norm_rec) in enumerate(zip(raw_records, normalized)):
                db_record = StructuredRecord(
                    dataset_id=dataset.id,
                    source_id=source_id,
                    entity_id=entity.id,
                    record_index=idx,
                    original_row_number=idx+1,
                    raw_data=raw_rec,
                    normalized_data=norm_rec
                )
                db.add(db_record)
                
                # Create a text chunk for hybrid retrieval
                record_meta = metadata.copy()
                record_meta.update(norm_rec)
                record_meta["content_type"] = "structured_record"
                record_meta["dataset_type"] = dataset.dataset_type
                record_meta["entity_name"] = entity_name
                
                content_str = " | ".join(f"{k.capitalize()}: {v}" for k, v in raw_rec.items())
                docs.append(Document(page_content=content_str, metadata=record_meta))
                
            db.commit()
            
        # 3. Extract Explicit Facts
        facts = extract_explicit_facts(entity_name, text_content)
        for f in facts:
            db_fact = ExplicitFact(
                entity_id=entity.id,
                source_id=source_id,
                subject=f.get("subject", entity_name),
                predicate=f.get("predicate", "unknown"),
                object_val=str(f.get("object", "")),
                year=f.get("year"),
                position=f.get("position")
            )
            db.add(db_fact)
        db.commit()
                
        # 4. Clean & Chunk regular text
        if text_content and text_content.strip():
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200
            )
            raw_doc = Document(page_content=text_content, metadata=metadata)
            docs.extend(text_splitter.split_documents([raw_doc]))
        
        chunk_count = len(docs)
        
        # 5. Add complete metadata to each chunk
        for i, doc in enumerate(docs):
            doc.metadata.update({
                "persona_id": source_record.persona_id,
                "knowledge_source_id": source_id,
                "entity_id": entity.id,
                "entity_name": entity_name,
                "dataset_type": dataset.dataset_type if dataset else "text",
                "source_type": source_record.source_type,
                "source_name": source_record.name,
                "source_url": source_record.source_url or "",
                "chunk_index": i,
                "total_chunks": chunk_count
            })
            # Ensure no complex types in Chroma metadata (must be string, int, float, bool)
            doc.metadata = {k: v for k, v in doc.metadata.items() if isinstance(v, (str, int, float, bool))}
            
        # 6. Store in ChromaDB
        if chunk_count > 0:
            vector_store = get_vector_store()
            vector_store.add_documents(docs)
            
        # 7. Update Database Tracking
        source_record.chunk_count = chunk_count
        source_record.status = "COMPLETED"
        db.commit()

    except Exception as e:
        import traceback
        traceback.print_exc()
        source_record.status = "FAILED"
        source_record.error_message = str(e)
        db.commit()
    finally:
        db.close()

def get_all_knowledge_sources(persona_id: str):
    db = SessionLocal()
    sources = db.query(KnowledgeSource).filter(KnowledgeSource.persona_id == persona_id).order_by(KnowledgeSource.created_at.desc()).all()
    # Convert to dicts for API response
    result = []
    for s in sources:
        result.append({
            "id": s.id,
            "name": s.name,
            "source_type": s.source_type,
            "source_url": s.source_url,
            "status": s.status,
            "chunk_count": s.chunk_count,
            "source_count": s.source_count,
            "created_at": s.created_at.isoformat()
        })
    db.close()
    return result

def get_knowledge_source_status(source_id: str):
    db = SessionLocal()
    source = db.query(KnowledgeSource).filter(KnowledgeSource.id == source_id).first()
    db.close()
    if not source:
        return None
    return {
        "id": source.id,
        "status": source.status,
        "chunk_count": source.chunk_count,
        "error_message": source.error_message
    }

def delete_knowledge_source(source_id: str):
    db = SessionLocal()
    source = db.query(KnowledgeSource).filter(KnowledgeSource.id == source_id).first()
    if source:
        # Delete from ChromaDB
        vector_store = get_vector_store()
        collection = vector_store._collection
        collection.delete(where={"knowledge_source_id": source_id})
        
        # Delete from DB
        db.delete(source)
        db.commit()
    db.close()
