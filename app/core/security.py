# =============================================================================
# app/core/security.py
# =============================================================================
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from fastapi import HTTPException, status
from app.core.config import settings
from app.core.logger import get_module_logger

logger = get_module_logger(__name__, "logs/security.log")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        logger.info(f"Creating token with custom expiration: {expires_delta}")
        if not isinstance(expires_delta, timedelta):
            logger.error("Invalid type for expires_delta, expected timedelta")
            raise ValueError("expires_delta must be a timedelta object")
        expire = datetime.utcnow() + expires_delta
    else:
        logger.warning("No expiration delta provided, using default settings.")
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> str:
    """Verify JWT token and return email"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            logger.error("Token does not contain 'sub' field with email")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return email
    except JWTError:
        logger.error("JWT token verification failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
