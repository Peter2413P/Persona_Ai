import sys
import os
import asyncio
from typing import List, Dict

# Ensure backend root is in PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.chat_service import _classify_intent_and_route, stream_chat_response
from app.rag.llm import get_llm
from app.db.session import Base, engine

# Ensure DB is created for tests if running standalone
Base.metadata.create_all(bind=engine)

async def run_test(query: str):
    print(f"\n{'='*50}\nTESTING: {query}\n{'='*50}")
    llm = get_llm()
    
    # Check Classification
    route, intent = _classify_intent_and_route(query, llm)
    print(f"CLASSIFIED -> Route: {route}, Intent: {intent}\n")
    
    print("RESPONSE:")
    async for chunk in stream_chat_response(query, []):
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
    queries = [
        "Who is Vijay?", # Should be NORMAL
        "What was Vijay's first major film?", # Should be DETAILED
        "List all movies of Vijay", # Should be COMPREHENSIVE_LIST
        "Give Vijay's complete filmography year by year", # Should be COMPREHENSIVE_LIST
        "Tell me about the movie Vijay acted in called 'Galactic Avengers 3000'" # Fake movie hallucination test
    ]
    
    for q in queries:
        await run_test(q)

if __name__ == "__main__":
    asyncio.run(main())
