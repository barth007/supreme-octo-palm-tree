# =============================================================================
# app/api/v1/endpoints/auth.py (Updated Google OAuth callback)
# =============================================================================
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from urllib.parse import urlencode
from datetime import datetime
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
    
    logger.info("Redirecting to Google for authentication")
    logger.debug(f"Redirect URI: {redirect_uri}")
    
    if not redirect_uri.startswith("http"):
        logger.error("Invalid redirect URI format")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid redirect URI format"
        )
    
    return await oauth.google.authorize_redirect(request, redirect_uri)

@router.get("/google/callback", status_code=status.HTTP_302_FOUND)
async def google_callback(request: Request, db: Session = Depends(get_db)):
    """Handle Google OAuth2 callback and redirect to frontend"""
    try:
        # Get the token from Google
        token = await oauth.google.authorize_access_token(request)
        if not token:
            logger.error("Failed to retrieve token from Google")
            return _redirect_to_frontend_with_error("Failed to retrieve token from Google")
        
        logger.info("Successfully retrieved token from Google")
        logger.debug(f"Token: {token}")
        
        if "error" in token:
            logger.error(f"Error in token response: {token['error']}")
            return _redirect_to_frontend_with_error(f"OAuth error: {token['error']}")
        
        # Get user info from Google
        user_info = token.get('userinfo')
        if not user_info:
            user_info = await AuthService.get_google_user_info(token["access_token"])
        
        # Process user and create token
        token_response = await AuthService.process_google_user(db, user_info)
        
        logger.info(f"User authenticated successfully: {user_info.get('email')}")
        
        # Redirect to frontend with success and token
        return _redirect_to_frontend_with_success(token_response)
        
    except Exception as e:
        logger.error(f"Authentication failed: {str(e)}")
        return _redirect_to_frontend_with_error(f"Authentication failed: {str(e)}")

def _redirect_to_frontend_with_success(token_response: TokenResponse) -> RedirectResponse:
    """Redirect to frontend with successful authentication data"""
    
    # Frontend URL - configure this in your settings
    frontend_base_url = getattr(settings, 'FRONTEND_BASE_URL', 'http://localhost:3000')
    
    # Create query parameters for the frontend
    query_params = {
        'success': 'true',
        'token': token_response.access_token,
        'user_id': token_response.user.id,
        'user_name': token_response.user.name,
        'user_email': token_response.user.email,
    }
    
    # Add profile image if available
    if token_response.user.profile_image:
        query_params['profile_image'] = token_response.user.profile_image
    
    # Add Slack connection status
    if token_response.user.slack_connection:
        query_params['slack_connected'] = 'true'
        query_params['slack_team'] = token_response.user.slack_connection.team_name
    else:
        query_params['slack_connected'] = 'false'
    
    # Build the redirect URL
    redirect_url = f"{frontend_base_url}/auth/callback?{urlencode(query_params)}"
    
    logger.info(f"Redirecting to frontend: {frontend_base_url}/auth/callback")
    
    return RedirectResponse(url=redirect_url, status_code=302)

def _redirect_to_frontend_with_error(error_message: str) -> RedirectResponse:
    """Redirect to frontend with error information"""
    
    # Frontend URL - configure this in your settings  
    frontend_base_url = getattr(settings, 'FRONTEND_BASE_URL', 'http://localhost:3000')
    
    # Create error query parameters
    query_params = {
        'success': 'false',
        'error': error_message,
        'timestamp': str(int(datetime.utcnow().timestamp()))
    }
    
    # Build the redirect URL
    redirect_url = f"{frontend_base_url}/auth/callback?{urlencode(query_params)}"
    
    logger.warning(f"Redirecting to frontend with error: {error_message}")
    
    return RedirectResponse(url=redirect_url, status_code=302)

# Keep this endpoint for API-only usage (mobile apps, etc.)
@router.post("/google/token", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def google_token_exchange(request: Request, db: Session = Depends(get_db)):
    """
    Alternative endpoint for API-only Google OAuth token exchange
    Use this for mobile apps or when you need JSON response instead of redirect
    """
    try:
        # Get the token from Google
        token = await oauth.google.authorize_access_token(request)
        if not token:
            logger.error("Failed to retrieve token from Google")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to retrieve token from Google"
            )
        
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