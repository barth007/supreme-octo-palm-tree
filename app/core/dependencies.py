# =============================================================================
# app/core/dependencies.py
# =============================================================================
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.user import User
from app.core.security import verify_token
from app.core.logger import get_module_logger


logger = get_module_logger(__name__, "logs/dependencies.log")

security = HTTPBearer()

def get_current_user_email(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Get current user email from JWT token"""
    logger.info(f"Verifying token for user email")
    return verify_token(credentials.credentials)

def get_current_user(
    email: str = Depends(get_current_user_email),
    db: Session = Depends(get_db)
) -> User:
    """Get current user from database"""
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        logger.error(f"User not found: {email}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    logger.info(f"Current user retrieved: {user.email}")
    return user