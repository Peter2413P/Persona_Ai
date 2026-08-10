from langchain_community.document_loaders import (
    PyMuPDFLoader,
    Docx2txtLoader,
    UnstructuredPowerPointLoader,
    CSVLoader,
    TextLoader,
    UnstructuredMarkdownLoader
)

def get_loader_for_file(file_path: str):
    ext = file_path.split('.')[-1].lower()
    
    if ext == 'pdf':
        return PyMuPDFLoader(file_path)
    elif ext == 'docx':
        return Docx2txtLoader(file_path)
    elif ext == 'pptx':
        return UnstructuredPowerPointLoader(file_path)
    elif ext == 'csv':
        return CSVLoader(file_path)
    elif ext == 'txt':
        return TextLoader(file_path, autodetect_encoding=True)
    elif ext == 'md':
        return UnstructuredMarkdownLoader(file_path)
    else:
        raise ValueError(f"Unsupported file extension: {ext}")
