"""
Configuration management for PCB Analyzer backend
"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Supabase
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    
    # Database
    database_url: str = ""
    
    # Server
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    
    # File uploads
    upload_dir: str = "./uploads"
    max_upload_size: int = 524288000  # 500MB (increased from 100MB)
    
    # Performance settings
    max_workers: int = 16  # Parallel workers for DRC
    enable_caching: bool = True
    cache_ttl: int = 3600  # Cache TTL in seconds
    
    model_config = SettingsConfigDict(
        extra="ignore",  # Ignore extra fields like VITE_* from .env
        env_file="../.env",
        env_file_encoding="utf-8"
    )
    
    # Environment
    python_env: str = "development"
    
    # CORS
    cors_origins: list = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ]
    
    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-2024-08-06"
    enable_ai_analysis: bool = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Create uploads directory if it doesn't exist
def ensure_upload_dir():
    """Ensure upload directory exists"""
    settings = get_settings()
    upload_path = Path(settings.upload_dir)
    upload_path.mkdir(parents=True, exist_ok=True)
    return upload_path
