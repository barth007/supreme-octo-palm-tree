# =============================================================================
# app/core/config.py
# =============================================================================
from typing import List, Optional
from pydantic import  field_validator
from pydantic_settings import BaseSettings
import os
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # Project Info
    PROJECT_NAME: str = "FastAPI OAuth2 Backend"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = "Scalable FastAPI backend with Google OAuth2"
    API_V1_STR: str = "/api/v1"
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Google OAuth2
    print(f'GOOGLE_CLIENT_ID: {os.getenv("GOOGLE_CLIENT_ID")}')
    print(f'GOOGLE_CLIENT_SECRET: {os.getenv("GOOGLE_CLIENT_SECRET")}')
    print(f'GOOGLE_REDIRECT_URI: {os.getenv("GOOGLE_REDIRECT_URI")}')  
    GOOGLE_CLIENT_ID: Optional[str] = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET: Optional[str] = os.getenv("GOOGLE_CLIENT_SECRET")
    GOOGLE_REDIRECT_URI: str = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/v1/auth/google/callback")
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./app.db")
    
    # CORS
    ALLOWED_HOSTS: List[str] = ["*"]  # Configure for production
    
    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = ENVIRONMENT == "development"

    @field_validator("GOOGLE_CLIENT_ID")
    @classmethod
    def validate_google_client_id(cls, v):
        if not v:
            raise ValueError("GOOGLE_CLIENT_ID is required")
        return v

    @field_validator("GOOGLE_CLIENT_SECRET")
    @classmethod
    def validate_google_client_secret(cls, v):
        if not v:
            raise ValueError("GOOGLE_CLIENT_SECRET is required")
        return v

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()