# =============================================================================
# app/api/v1/endpoints/users.py
# =============================================================================
from fastapi import APIRouter, Depends
from app.schemas.user import UserResponse
from app.core.dependencies import get_current_user
from app.models.user import User
from app.core.logger import get_module_logger


logger = get_module_logger(__name__, "logs/users.log")


router = APIRouter()

@router.get("/me", response_model=UserResponse, status_code=200)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    logger.info(f"Fetching information for user: {current_user.email}")
    return UserResponse(
        id=str(current_user.id),
        name=current_user.name,
        email=current_user.email,
        profile_image=current_user.profile_image,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at
    )