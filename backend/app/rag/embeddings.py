from langchain_huggingface import HuggingFaceEmbeddings
from functools import lru_cache

@lru_cache(maxsize=1)
def get_embeddings_model():
    model_name = "BAAI/bge-base-en-v1.5"
    model_kwargs = {'device': 'cpu'} # Change to cuda if GPU is available
    encode_kwargs = {'normalize_embeddings': True}
    return HuggingFaceEmbeddings(
        model_name=model_name,
        model_kwargs=model_kwargs,
        encode_kwargs=encode_kwargs
    )
