import sys
import os
import asyncio
from app.db.session import SessionLocal, Base, engine
from app.db.models import KnowledgeSource
from app.services.research_service import auto_research_background

# Ensure DB is created
Base.metadata.create_all(bind=engine)

def seed_db():
    db = SessionLocal()
    # Create source record
    source = KnowledgeSource(
        name="Vijay (actor)",
        source_type="AUTO_RESEARCH",
        topic="Vijay (actor)",
        status="PROCESSING"
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    source_id = source.id
    db.close()
    
    print("Fetching and ingesting Wikipedia page for 'Vijay (actor)'...")
    # Run the background task synchronously for the test setup
    auto_research_background(source_id, "Vijay (actor)", use_wikipedia=True, use_web=False)
    
    db = SessionLocal()
    updated_source = db.query(KnowledgeSource).filter(KnowledgeSource.id == source_id).first()
    print(f"Ingestion Status: {updated_source.status}")
    print(f"Chunks Created: {updated_source.chunk_count}")
    db.close()

if __name__ == "__main__":
    seed_db()
