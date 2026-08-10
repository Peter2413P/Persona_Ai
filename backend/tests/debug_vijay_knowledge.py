import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.rag.database import get_vector_store
from app.db.session import SessionLocal
from app.db.models import Persona

def debug_chroma():
    db = SessionLocal()
    personas = db.query(Persona).all()
    print(f"Total Personas in PostgreSQL: {len(personas)}")
    
    if not personas:
        print("No personas found. Please ingest the data first.")
        return

    persona = personas[-1]  # Get the most recent persona
    print(f"\nTarget Persona: {persona.name} (ID: {persona.id})")
    db.close()

    vs = get_vector_store()
    collection = vs._collection
    
    # Get all chunks for this persona
    results = collection.get(where={"persona_id": persona.id})
    ids = results["ids"]
    metadatas = results["metadatas"]
    documents = results["documents"]
    
    print(f"\n==================================================")
    print(f"STEP 1: VERIFY THE INGESTED DATA")
    print(f"==================================================")
    print(f"Total chunks in ChromaDB for persona: {len(ids)}")
    
    filmography_records = [m for m in metadatas if m.get("content_type") == "filmography_record"]
    print(f"Total filmography_record chunks: {len(filmography_records)}")
    
    if len(filmography_records) > 0:
        print("\nFirst 5 filmography records:")
        for r in filmography_records[:5]:
            print({k: v for k, v in r.items() if k in ['year', 'title', 'role', 'notes']})
            
        print("\nLast 5 filmography records:")
        for r in filmography_records[-5:]:
            print({k: v for k, v in r.items() if k in ['year', 'title', 'role', 'notes']})
            
    # Check for specific 2010-2020 movies
    print("\n==================================================")
    print(f"STEP 2: CHECK WHETHER THE COMPLETE TABLE WAS EXTRACTED")
    print(f"==================================================")
    movies_2010_2020 = [r for r in filmography_records if r.get("year", "").isdigit() and 2010 <= int(r.get("year", 0)) <= 2020]
    print(f"Movies from 2010 to 2020 found: {len(movies_2010_2020)}")
    for m in movies_2010_2020:
        print(f"{m.get('year')} | {m.get('title')}")

if __name__ == "__main__":
    debug_chroma()
