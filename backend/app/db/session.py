import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# SQLite database file in the backend directory
DB_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "knowledge.db")
SQLALCHEMY_DATABASE_URL = "sqlite:///./knowledge_v2.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
