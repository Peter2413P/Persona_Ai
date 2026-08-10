from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.endpoints import router as api_router

from app.db.session import engine, Base
from app.db import models
import os
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

# Create database tables
Base.metadata.create_all(bind=engine)

# Lightweight schema migration for existing SQLite DBs
try:
    from sqlalchemy import text
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE voice_profiles ADD COLUMN provider_metadata_json TEXT DEFAULT '{}'"))
        conn.commit()
except Exception:
    pass

app = FastAPI(
    title="PersonaForge AI",
    description="Intelligent chatbot platform using RAG, local LLMs, and internet search.",
    version="0.1.0",
)

# Configure CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development; restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
