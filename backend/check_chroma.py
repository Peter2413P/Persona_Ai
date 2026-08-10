from app.rag.database import get_vector_store
import json

vs = get_vector_store()
results = vs._collection.get()
for i, m in enumerate(results["metadatas"]):
    if m and "vetri" in str(m.get("title", "")).lower():
        print("FOUND VETRI:")
        print(json.dumps(m, indent=2))
