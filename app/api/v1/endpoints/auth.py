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
from app.core.logger import get_module_logger
logger = get_module_logger(__name__, "logs/auth.log")

router = APIRouter()

@router.get("/google/login", status_code=status.HTTP_302_FOUND)
async def google_login(request: Request):
    """Initiate Google OAuth2 login"""
    redirect_uri = settings.GOOGLE_REDIRECT_URI
    if not redirect_uri:
        logger.error("Google redirect URI is not configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google redirect URI is not configured"
        )
    if not oauth.google:
        logger.error("Google OAuth2 client is not configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth2 client is not configured"
        )
    # Redirect to Google for authentication
    logger.info("Redirecting to Google for authentication")
    logger.debug(f"Redirect URI: {redirect_uri}")
    if not redirect_uri.startswith("http"):
        logger.error("Invalid redirect URI format")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid redirect URI format"
        )
    return await oauth.google.authorize_redirect(request, redirect_uri)

@router.get("/google/callback", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def google_callback(request: Request, db: Session = Depends(get_db)):
    """Handle Google OAuth2 callback"""
    try:
        # Get the token from Google
        token = await oauth.google.authorize_access_token(request)
        if not token:
            logger.error("Failed to retrieve token from Google")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to retrieve token from Google"
            )
        logger.info("Successfully retrieved token from Google")
        logger.debug(f"Token: {token}")
        if "error" in token:
            logger.error(f"Error in token response: {token['error']}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error in token response: {token['error']}"
            )
        # Get user info from Google
        user_info = token.get('userinfo')
        if not user_info:
            user_info = await AuthService.get_google_user_info(token["access_token"])
        
        # Process user and create token
        return await AuthService.process_google_user(db, user_info)
        
    except Exception as e:
        logger.error(f"Authentication failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Authentication failed: {str(e)}"
        )

@router.post("/refresh", response_model=TokenResponse, status_code=status.HTTP_200_OK)
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