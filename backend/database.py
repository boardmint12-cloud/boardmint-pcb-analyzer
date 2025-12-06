"""
Database connection and session management
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import get_settings
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

# Base class for models
Base = declarative_base()

# Create database engine - use SQLite fallback if no DATABASE_URL
database_url = settings.database_url
if not database_url or database_url == "":
    # Use in-memory SQLite as fallback (app uses Supabase API for main data)
    database_url = "sqlite:///./app.db"
    logger.warning("No DATABASE_URL configured, using local SQLite database")

try:
    if database_url.startswith("sqlite"):
        engine = create_engine(database_url, connect_args={"check_same_thread": False})
    else:
        engine = create_engine(
            database_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10
        )
except Exception as e:
    logger.warning(f"Failed to create database engine: {e}")
    engine = create_engine("sqlite:///./app.db", connect_args={"check_same_thread": False})

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
