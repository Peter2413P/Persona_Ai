import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.rag.database import get_vector_store

def check_chroma():
    vector_store = get_vector_store()
    
    try:
        docs = vector_store.similarity_search_with_score(
            "List all movies of Vijay", 
            k=500,
            filter={"content_type": "filmography_record"}
        )
        print(f"Retrieved with content_type filter: {len(docs)}")
        if len(docs) > 0:
            print("Sample:")
            print(docs[0][0].metadata)
    except Exception as e:
        print(f"Exception with content_type filter: {e}")

if __name__ == "__main__":
    check_chroma()
