from langchain_chroma import Chroma
from app.rag.embeddings import get_embeddings_model
import os

DB_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "chroma_db")

def get_vector_store():
    embeddings = get_embeddings_model()
    return Chroma(
        collection_name="persona_forge_docs",
        embedding_function=embeddings,
        persist_directory="./chroma_db_v2"
    )
