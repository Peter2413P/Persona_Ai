from langchain_community.llms.ollama import Ollama

def get_llm():
    return Ollama(
        model="llama3.1:8b",
        temperature=0.1
    )
