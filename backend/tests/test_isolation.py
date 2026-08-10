import sys
import os
import asyncio
from typing import List, Dict

# Ensure backend root is in PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.chat_service import stream_chat_response
from app.db.session import Base, engine, SessionLocal
from app.db.models import Persona, KnowledgeSource
from app.services.research_service import ingest_url_background
from app.rag.database import get_vector_store

Base.metadata.create_all(bind=engine)

def setup_test_data():
    db = SessionLocal()
    # Clean up old data
    db.query(Persona).delete()
    db.commit()

    # Create Persona A (Vijay)
    persona_a = Persona(name="Thalapathy Vijay")
    db.add(persona_a)
    db.commit()
    db.refresh(persona_a)

    # Create Persona B (Rajinikanth)
    persona_b = Persona(name="Rajinikanth")
    db.add(persona_b)
    db.commit()
    db.refresh(persona_b)
    
    # Add sources
    source_a = KnowledgeSource(
        persona_id=persona_a.id,
        name="Vijay (actor)",
        source_type="WIKIPEDIA",
        source_url="https://en.wikipedia.org/wiki/Vijay_(actor)",
        status="PROCESSING"
    )
    db.add(source_a)
    
    source_a_film = KnowledgeSource(
        persona_id=persona_a.id,
        name="Vijay filmography",
        source_type="WIKIPEDIA",
        source_url="https://en.wikipedia.org/wiki/Vijay_filmography",
        status="PROCESSING"
    )
    db.add(source_a_film)
    
    source_b = KnowledgeSource(
        persona_id=persona_b.id,
        name="Rajinikanth",
        source_type="WIKIPEDIA",
        source_url="https://en.wikipedia.org/wiki/Rajinikanth",
        status="PROCESSING"
    )
    db.add(source_b)
    db.commit()
    db.refresh(source_a)
    db.refresh(source_b)
    
    persona_a_id = persona_a.id
    persona_b_id = persona_b.id
    
    source_a_id = source_a.id
    source_a_url = source_a.source_url
    source_a_film_id = source_a_film.id
    source_a_film_url = source_a_film.source_url
    source_b_id = source_b.id
    source_b_url = source_b.source_url
    
    db.close()
    
    # Process them synchronously for testing
    print("Ingesting Wikipedia data for Persona A...")
    ingest_url_background(source_a_id, source_a_url)
    ingest_url_background(source_a_film_id, source_a_film_url)
    
    print("Ingesting Wikipedia data for Persona B...")
    ingest_url_background(source_b_id, source_b_url)
    
    return persona_a_id, persona_b_id

async def run_chat(persona_id: str, query: str):
    print(f"\n{'='*50}\nTESTING: {query}\nPERSONA ID: {persona_id}\n{'='*50}")
    
    print("RESPONSE:")
    async for chunk in stream_chat_response(persona_id, query, []):
        import json
        if chunk.startswith("data: "):
            try:
                data = json.loads(chunk[6:])
                if data["type"] == "sources":
                    print(f"[SOURCES IDENTIFIED]: {len(data['sources'])}")
                    for s in data["sources"]:
                        print(f"  - {s['title']}")
                    print("-" * 30)
                elif data["type"] == "token":
                    print(data["content"], end="", flush=True)
                elif data["type"] == "error":
                    print(f"\n[ERROR]: {data['message']}")
            except:
                pass
    print("\n")

async def main():
    print("Setting up personas and knowledge bases...")
    persona_a_id, persona_b_id = setup_test_data()
    
    # Test 1: Ask Persona A about his movies (Isolation Check)
    await run_chat(persona_a_id, "What movies has Vijay acted in? Give me a list.")
    
    # Test 2: Comprehensive List intent
    await run_chat(persona_a_id, "List all movies of Vijay")
    
    # Test 3: Chronological order
    await run_chat(persona_a_id, "List all Vijay movies in chronological order")
    
    # Test 4: First film
    await run_chat(persona_a_id, "What was Vijay's first film?")
    
    # Test 5: Filter by year
    await run_chat(persona_a_id, "List Vijay's movies from 2010 to 2020")
    
    # Test 6: Ask Persona A about Rajinikanth (Cross-Persona Leak Check)
    await run_chat(persona_a_id, "Who is Rajinikanth?")
    
    # Test 7: Ask Persona B about Rajinikanth
    await run_chat(persona_b_id, "Who is Rajinikanth?")
    
    # Verify Deletion Purge
    # print("\nDeleting Persona A...")
    # from app.api.endpoints import delete_persona
    # delete_persona(persona_a_id)
    # print("Verifying ChromaDB...")
    # vs = get_vector_store()
    # try:
    #     results = vs._collection.get(where={"persona_id": persona_a_id})
    #     if len(results["ids"]) == 0:
    #         print("SUCCESS: Persona A chunks deleted from ChromaDB.")
    #     else:
    #         print("ERROR: Persona A chunks still exist!")
    # except Exception as e:
    #     print(f"ChromaDB check error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
