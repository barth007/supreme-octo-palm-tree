# =============================================================================
# app/services/auth_service.py
# =============================================================================
from datetime import timedelta
from typing import Dict, Any
from sqlalchemy.orm import Session
import httpx
from app.core.config import settings
from app.core.security import create_access_token
from app.schemas.user import UserCreate, UserUpdate
from app.schemas.token import TokenResponse, TokenData
from app.services.user_service import UserService
from app.schemas.user import UserResponse, GoogleUserInfo
from pydantic import ValidationError


from app.core.logger import get_module_logger


logger = get_module_logger(__name__, "logs/auth_service.log")

class AuthService:
    """Service for handling authentication logic"""

    @staticmethod
    async def process_google_user(db: Session, user_info: Dict[str, Any]) -> TokenResponse:
        """Process Google user info and return token"""

        try:
            user_info_data = GoogleUserInfo(**user_info)
        except ValidationError as e:
            logger.error(f"Invalid Google user data: {e}")
            raise ValueError("Invalid user data from Google")

        email = user_info.get('email')
        name = user_info.get('name')
        picture = user_info.get('picture')

        # Get or create user
        user = UserService.get_user_by_email(db, email)
        if not user:
            user_data = UserCreate(
                name=name or email.split('@')[0],
                email=email,
                profile_image=picture
            )
            user = UserService.create_user(db, user_data)
        else:
            # Update user info if needed
            update_data = UserUpdate(
                name=name or user.name,
                profile_image=picture or user.profile_image
            )
            user = UserService.update_user(db, user, update_data)
        
        # Create access token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.email}, 
            expires_delta=access_token_expires
        )
        
        # Convert user to response model
        user_response = UserResponse(
            id=str(user.id),
            name=user.name,
            email=user.email,
            profile_image=user.profile_image,
            created_at=user.created_at,
            updated_at=user.updated_at
        )
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user=user_response
        )

    @staticmethod
    async def get_google_user_info(token: str) -> Dict[str, Any]:
        """Get user info from Google API"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                'https://www.googleapis.com/oauth2/v2/userinfo',
                headers={'Authorization': f'Bearer {token}'}
            )
            return response.json()