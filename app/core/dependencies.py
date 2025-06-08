# =============================================================================
# app/core/dependencies.py
# =============================================================================
from fastapi import Depends, HTTPException, status, Request, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.user import User
from app.core.security import verify_token
from app.core.logger import get_module_logger
from typing import Optional

logger = get_module_logger(__name__, "logs/dependencies.log")

security = HTTPBearer(auto_error=False)  # Don't auto-error, handle manually

def get_current_user_email_flexible(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    token: Optional[str] = Query(None, description="JWT token as query parameter")
) -> str:
    """Get current user email from JWT token (header or query param)"""
    
    token_to_verify = None
    
    # Try to get token from Authorization header first
    if credentials:
        token_to_verify = credentials.credentials
        logger.info("Using token from Authorization header")
    
    # Fallback to query parameter
    elif token:
        token_to_verify = token
        logger.info("Using token from query parameter")
    
    if not token_to_verify:
        logger.error("No token provided in header or query params")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No authentication token provided",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    logger.info("Verifying token for user email")
    return verify_token(token_to_verify)

def get_current_user_flexible(
    email: str = Depends(get_current_user_email_flexible),
    db: Session = Depends(get_db)
) -> User:
    """Get current user from database (supports both header and query token)"""
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        logger.error(f"User not found: {email}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    logger.info(f"Current user retrieved: {user.email}")
    return user

# Original functions for backward compatibility
def get_current_user_email(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Get current user email from JWT token (header only)"""
    if credentials is None:
        logger.error("No token provided in Authorization header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No authentication token provided",
            headers={"WWW-Authenticate": "Bearer"},
        )
    logger.info("Verifying token for user email")
    return verify_token(credentials.credentials)

def get_current_user(
    email: str = Depends(get_current_user_email),
    db: Session = Depends(get_db)
) -> User:
    """Get current user from database (header token only)"""
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        logger.error(f"User not found: {email}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    logger.info(f"Current user retrieved: {user.email}")
    return user