# =============================================================================
# app/core/config.py
# =============================================================================
from typing import List, Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings
import os
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # Project Info
    PROJECT_NAME: str = "PR Reminder API"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = "Scalable FastAPI backend for PR reminders with Google OAuth2 and Slack integration"
    API_V1_STR: str = "/api/v1"
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "720"))  # 12 hours for production
    
    # Frontend Configuration
    FRONTEND_BASE_URL: str = os.getenv("FRONTEND_BASE_URL", "http://localhost:3000")
    
    # Google OAuth2 
    GOOGLE_CLIENT_ID: Optional[str] = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET: Optional[str] = os.getenv("GOOGLE_CLIENT_SECRET")
    GOOGLE_REDIRECT_URI: str = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/v1/auth/google/callback")

    # Slack OAuth2
    SLACK_CLIENT_ID: Optional[str] = os.getenv("SLACK_CLIENT_ID")
    SLACK_CLIENT_SECRET: Optional[str] = os.getenv("SLACK_CLIENT_SECRET")
    SLACK_REDIRECT_URI: str = os.getenv("SLACK_REDIRECT_URI", "http://localhost:8000/api/v1/auth/slack/callback")

    # Postmark webhooks Authentication (HTTP Basic Auth)
    WEBHOOK_USERNAME: str = os.getenv("WEBHOOK_USERNAME", "webhook_user")
    WEBHOOK_PASSWORD: str = os.getenv("WEBHOOK_PASSWORD", "webhook_password")

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./app.db")
    
    # CORS
    ALLOWED_HOSTS: List[str] = ["*"]  # Configure for production
    
    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = ENVIRONMENT == "development"
    
    # Production-specific settings
    DATABASE_POOL_SIZE: int = int(os.getenv("DATABASE_POOL_SIZE", "10"))
    DATABASE_MAX_OVERFLOW: int = int(os.getenv("DATABASE_MAX_OVERFLOW", "20"))
    
    # Render.com specific
    PORT: int = int(os.getenv("PORT", "8000"))

    @field_validator("GOOGLE_CLIENT_ID")
    @classmethod
    def validate_google_client_id(cls, v):
        if not v:
            print("⚠️  WARNING: GOOGLE_CLIENT_ID is not set")
        return v

    @field_validator("GOOGLE_CLIENT_SECRET")
    @classmethod
    def validate_google_client_secret(cls, v):
        if not v:
            print("⚠️  WARNING: GOOGLE_CLIENT_SECRET is not set")
        return v
    
    @field_validator("SLACK_CLIENT_ID")
    @classmethod
    def validate_slack_client_id(cls, v):
        if not v:
            print("⚠️  WARNING: SLACK_CLIENT_ID is not set")
        return v
        
    @field_validator("SLACK_CLIENT_SECRET")
    @classmethod
    def validate_slack_client_secret(cls, v):
        if not v:
            print("⚠️  WARNING: SLACK_CLIENT_SECRET is not set")
        return v
    
    @field_validator("WEBHOOK_USERNAME")
    @classmethod
    def validate_webhook_username(cls, v):
        if not v:
            print("⚠️  WARNING: WEBHOOK_USERNAME is not set")
        return v
        
    @field_validator("WEBHOOK_PASSWORD")
    @classmethod
    def validate_webhook_password(cls, v):
        if not v:
            print("⚠️  WARNING: WEBHOOK_PASSWORD is not set")
        return v

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()