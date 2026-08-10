import asyncio
import httpx
import json
import time
import os

BASE_URL = "http://localhost:8000"

def wait_for_server():
    print("Waiting for server to start...")
    for _ in range(10):
        try:
            r = httpx.get(f"{BASE_URL}/docs")
            if r.status_code == 200:
                print("Server is up!")
                return True
        except:
            pass
        time.sleep(1)
    return False

async def main():
    if not wait_for_server():
        print("Server failed to start")
        return
        
    async with httpx.AsyncClient(timeout=60.0) as client:
        # 1. Create a Generic Persona
        print("\n--- 1. Creating Persona ---")
        r = await client.post(f"{BASE_URL}/personas", json={"name": "Vijay"})
        persona = r.json()
        persona_id = persona["id"]
        print(f"Created Persona: {persona_id}")
        
        # 2. Ingest a Wikipedia page
        print("\n--- 2. Ingesting Wikipedia Data ---")
        wiki_url = "https://en.wikipedia.org/wiki/Vijay_filmography"
        r = await client.post(f"{BASE_URL}/knowledge/url", json={
            "persona_id": persona_id,
            "url": wiki_url
        })
        print(f"Ingestion started: {r.json()}")
        source_id = r.json()["id"]
        
        # Wait for processing
        print("Waiting for ingestion to complete...")
        for _ in range(30):
            r = await client.get(f"{BASE_URL}/documents?persona_id={persona_id}")
            sources = r.json()
            source = next((s for s in sources if s["id"] == source_id), None)
            if source and source["status"] == "COMPLETED":
                print(f"Ingestion COMPLETED! {source['chunk_count']} chunks.")
                break
            elif source and source["status"] == "FAILED":
                print("Ingestion FAILED")
                return
            print(".", end="", flush=True)
            time.sleep(5)
            
        print("\n")
        
        # 3. Test Structured Queries
        test_queries = [
            "What was Vijay's first film?",
            "What was Vijay's first film as a lead actor?",
            "What was Vijay's final film?",
            "List all films in which Vijay had a guest appearance, cameo, or extended cameo.",
            "Which films featured Vijay in multiple roles?",
            "Which films did Vijay act in during 1995?",
            "What roles did Vijay play in Mersal?"
        ]
        
        print("\n--- 3. Testing Queries ---")
        for q in test_queries:
            print(f"\nQuery: {q}")
            try:
                # Use SSE stream
                async with client.stream("POST", f"{BASE_URL}/chat/stream", json={
                    "persona_id": persona_id,
                    "message": q,
                    "history": []
                }) as response:
                    print("Response: ", end="")
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = json.loads(line[6:])
                            if data["type"] == "token":
                                print(data["content"], end="", flush=True)
                            elif data["type"] == "error":
                                print(f"\nError: {data['message']}")
                    print("\n")
            except Exception as e:
                print(f"\nRequest failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
