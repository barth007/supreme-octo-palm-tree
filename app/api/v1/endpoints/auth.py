# =============================================================================
# app/api/v1/endpoints/auth.py
# =============================================================================
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services.auth_service import AuthService
from app.schemas.token import TokenResponse
from app.schemas.user import UserResponse
from app.core.dependencies import get_current_user
from app.models.user import User
from app.utils.oauth import oauth
from app.core.config import settings

router = APIRouter()

@router.get("/google/login")
async def google_login(request: Request):
    """Initiate Google OAuth2 login"""
    redirect_uri = settings.GOOGLE_REDIRECT_URI
    return await oauth.google.authorize_redirect(request, redirect_uri)

@router.get("/google/callback", response_model=TokenResponse)
async def google_callback(request: Request, db: Session = Depends(get_db)):
    """Handle Google OAuth2 callback"""
    try:
        # Get the token from Google
        token = await oauth.google.authorize_access_token(request)
        
        # Get user info from Google
        user_info = token.get('userinfo')
        if not user_info:
            # Fallback: fetch user info manually
            user_info = await AuthService.get_google_user_info(token["access_token"])
        
        # Process user and create token
        return await AuthService.process_google_user(db, user_info)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Authentication failed: {str(e)}"
        )

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(current_user: User = Depends(get_current_user)):
    """Refresh JWT token"""
    from datetime import timedelta
    from app.core.security import create_access_token
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": current_user.email}, 
        expires_delta=access_token_expires
    )
    
    user_response = UserResponse(
        id=str(current_user.id),
        name=current_user.name,
        email=current_user.email,
        profile_image=current_user.profile_image,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=user_response
    )