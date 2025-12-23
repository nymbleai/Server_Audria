from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    # Environment configuration
    environment: str = os.getenv("ENVIRONMENT", "development")
    
    # Supabase configuration
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_key: str = os.getenv("SUPABASE_KEY", "")
    
    # Database configuration (for SQLAlchemy - connects to Supabase PostgreSQL)
    database_url: Optional[str] = os.getenv("DATABASE_URL", "")
    database_echo: bool = os.getenv("DATABASE_ECHO", "false").lower() == "true"
    
    # Frontend URL (for CORS and password reset redirects)
    frontend_url: str = os.getenv("FRONTEND_URL", "http://localhost:5173")
    
    # JWT configuration (used by Supabase)
    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-this")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 30
    
    # Voice processing configuration
    voice_upload_folder: str = os.getenv("VOICE_UPLOAD_FOLDER", "./uploads/voices")
    tts_model: str = os.getenv("TTS_MODEL", "tts_models/multilingual/multi-dataset/xtts_v2")
    
    class Config:
        env_file = ".env"


settings = Settings()
