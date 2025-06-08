# =============================================================================
# app/api/v1/endpoints/slack_auth.py
# =============================================================================

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from urllib.parse import urlencode
from datetime import datetime
import uuid
from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services.slack_service import SlackService
from app.schemas.slack import SlackConnectionCreate, SlackConnectionResponse, SlackTestMessageRequest, SlackMessageRequest
from app.utils.oauth import oauth
from app.core.config import settings
from app.core.logger import get_module_logger
from typing import Dict, Any

logger = get_module_logger(__name__, "logs/slack_auth.log")

router = APIRouter()

# =============================================================================
# NEW REST ENDPOINT: Get Slack OAuth URL
# =============================================================================
@router.get("/slack/auth-url", status_code=status.HTTP_200_OK)
async def get_slack_auth_url(
    current_user: User = Depends(get_current_user)
) -> Dict[str, str]:
    """
    Get Slack OAuth authorization URL for the authenticated user
    
    This follows REST guidelines:
    - Uses standard Authorization header authentication
    - Returns JSON response instead of redirecting
    - Allows frontend to control the OAuth flow
    """
    logger.info(f"Generating Slack OAuth URL for user: {current_user.email}")
    
    # Validate Slack configuration
    if not settings.SLACK_CLIENT_ID or not settings.SLACK_CLIENT_SECRET:
        logger.error("Slack OAuth2 credentials are not configured")
        logger.error(f"SLACK_CLIENT_ID: {'SET' if settings.SLACK_CLIENT_ID else 'NOT SET'}")
        logger.error(f"SLACK_CLIENT_SECRET: {'SET' if settings.SLACK_CLIENT_SECRET else 'NOT SET'}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Slack OAuth2 is not configured"
        )
    
    redirect_uri = settings.SLACK_REDIRECT_URI
    
    # Generate secure state parameter with user ID
    state = f"user_{current_user.id}"
    
    # Define required Slack scopes
    scope = "chat:write users:read"
    
    # Build OAuth URL manually (more control than using oauth library for URL generation)
    auth_url = (
        f"https://slack.com/oauth/v2/authorize"
        f"?client_id={settings.SLACK_CLIENT_ID}"
        f"&scope={scope}"
        f"&redirect_uri={redirect_uri}"
        f"&state={state}"
        f"&response_type=code"
    )
    
    # Log OAuth parameters for debugging
    logger.info(f"OAuth parameters:")
    logger.info(f"  - client_id: {settings.SLACK_CLIENT_ID[:10]}...")
    logger.info(f"  - redirect_uri: {redirect_uri}")
    logger.info(f"  - state: {state}")
    logger.info(f"  - scope: {scope}")
    
    return {
        "auth_url": auth_url,
        "state": state,
        "redirect_uri": redirect_uri
    }

# =============================================================================
# OAUTH CALLBACK HANDLER
# =============================================================================

@router.get("/slack/callback", status_code=status.HTTP_302_FOUND)
async def slack_callback(request: Request, db: Session = Depends(get_db)):
    """
    Handle Slack OAuth2 callback and redirect to frontend
    """
    try:
        logger.info("Processing Slack OAuth callback")
        
        # Check for error parameters from Slack
        error = request.query_params.get("error")
        if error:
            error_description = request.query_params.get("error_description", "Unknown error")
            logger.error(f"Slack OAuth error: {error} - {error_description}")
            return _redirect_to_frontend_with_error(f"Slack authorization failed: {error_description}")
        
        # Get authorization code from Slack
        code = request.query_params.get("code")
        if not code:
            logger.error("No authorization code received from Slack")
            return _redirect_to_frontend_with_error("No authorization code received from Slack")
        
        # Validate state parameter
        state = request.query_params.get("state")
        if not state or not state.startswith("user_"):
            logger.error(f"Invalid or missing state parameter: {state}")
            return _redirect_to_frontend_with_error("Invalid state parameter")
        
        user_id_str = state.replace("user_", "")
        try:
            user_id = uuid.UUID(user_id_str)  # Convert string to UUID object
            logger.info(f"Processing OAuth callback for user UUID: {user_id}")
        except ValueError as e:
            logger.error(f"Invalid user ID format: {user_id_str} - {e}")
            return _redirect_to_frontend_with_error("Invalid user ID format")
        
        # Verify user exists
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.error(f"User not found: {user_id}")
            return _redirect_to_frontend_with_error("User not found")
        
        # Exchange authorization code for access token
        token_data = await _exchange_code_for_token(code)
        
        if not token_data.get("ok"):
            error_msg = token_data.get("error", "Token exchange failed")
            logger.error(f"Token exchange failed: {error_msg}")
            return _redirect_to_frontend_with_error(f"Token exchange failed: {error_msg}")
        
        # Extract token and user information
        access_token = token_data.get("access_token")
        authed_user = token_data.get("authed_user", {})
        team = token_data.get("team", {})
        
        slack_user_id = authed_user.get("id")
        slack_team_id = team.get("id")
        team_name = team.get("name")
        
        if not access_token or not slack_user_id or not slack_team_id:
            logger.error("Missing required Slack information in token response")
            logger.error(f"access_token: {'Present' if access_token else 'Missing'}")
            logger.error(f"slack_user_id: {slack_user_id}")
            logger.error(f"slack_team_id: {slack_team_id}")
            return _redirect_to_frontend_with_error("Missing required Slack information")
        
        # Create Slack connection in database
        slack_data = SlackConnectionCreate(
            slack_user_id=slack_user_id,
            slack_team_id=slack_team_id,
            access_token=access_token,
            team_name=team_name
        )
        
        slack_connection = SlackService.create_slack_connection(db, str(user_id), slack_data)
        
        logger.info(f"✅ Slack connection created successfully for user: {user.email}")
        logger.info(f"   Team: {team_name}")
        logger.info(f"   Slack User ID: {slack_user_id}")
        
        # Redirect to frontend with success
        return _redirect_to_frontend_with_slack_success(user, slack_connection)
        
    except Exception as e:
        logger.error(f"❌ Slack OAuth callback failed: {str(e)}", exc_info=True)
        return _redirect_to_frontend_with_error(f"Slack authentication failed: {str(e)}")
    """
    Handle Slack OAuth2 callback and redirect to frontend
    
    This endpoint:
    1. Receives the OAuth callback from Slack
    2. Exchanges authorization code for access token
    3. Stores the Slack connection in database
    4. Redirects to frontend with success/error status
    """
    try:
        logger.info("Processing Slack OAuth callback")
        
        # Check for error parameters from Slack
        error = request.query_params.get("error")
        if error:
            error_description = request.query_params.get("error_description", "Unknown error")
            logger.error(f"Slack OAuth error: {error} - {error_description}")
            return _redirect_to_frontend_with_error(f"Slack authorization failed: {error_description}")
        
        # Get authorization code from Slack
        code = request.query_params.get("code")
        if not code:
            logger.error("No authorization code received from Slack")
            return _redirect_to_frontend_with_error("No authorization code received from Slack")
        
        # Validate state parameter
        state = request.query_params.get("state")
        if not state or not state.startswith("user_"):
            logger.error(f"Invalid or missing state parameter: {state}")
            return _redirect_to_frontend_with_error("Invalid state parameter")
        
        user_id = state.replace("user_", "")
        logger.info(f"Processing OAuth callback for user: {user_id}")
        
        # Verify user exists
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.error(f"User not found: {user_id}")
            return _redirect_to_frontend_with_error("User not found")
        
        # Exchange authorization code for access token
        token_data = await _exchange_code_for_token(code)
        
        if not token_data.get("ok"):
            error_msg = token_data.get("error", "Token exchange failed")
            logger.error(f"Token exchange failed: {error_msg}")
            return _redirect_to_frontend_with_error(f"Token exchange failed: {error_msg}")
        
        # Extract token and user information
        access_token = token_data.get("access_token")
        authed_user = token_data.get("authed_user", {})
        team = token_data.get("team", {})
        
        slack_user_id = authed_user.get("id")
        slack_team_id = team.get("id")
        team_name = team.get("name")
        
        if not access_token or not slack_user_id or not slack_team_id:
            logger.error("Missing required Slack information in token response")
            logger.error(f"access_token: {'Present' if access_token else 'Missing'}")
            logger.error(f"slack_user_id: {slack_user_id}")
            logger.error(f"slack_team_id: {slack_team_id}")
            return _redirect_to_frontend_with_error("Missing required Slack information")
        
        # Create Slack connection in database
        slack_data = SlackConnectionCreate(
            slack_user_id=slack_user_id,
            slack_team_id=slack_team_id,
            access_token=access_token,
            team_name=team_name
        )
        
        slack_connection = SlackService.create_slack_connection(db, user_id, slack_data)
        
        logger.info(f"✅ Slack connection created successfully for user: {user.email}")
        logger.info(f"   Team: {team_name}")
        logger.info(f"   Slack User ID: {slack_user_id}")
        
        # Redirect to frontend with success
        return _redirect_to_frontend_with_slack_success(user, slack_connection)
        
    except Exception as e:
        logger.error(f"❌ Slack OAuth callback failed: {str(e)}", exc_info=True)
        return _redirect_to_frontend_with_error(f"Slack authentication failed: {str(e)}")

async def _exchange_code_for_token(code: str) -> Dict[str, Any]:
    """
    Exchange authorization code for access token using Slack API
    """
    import httpx
    
    url = "https://slack.com/api/oauth.v2.access"
    data = {
        "client_id": settings.SLACK_CLIENT_ID,
        "client_secret": settings.SLACK_CLIENT_SECRET,
        "code": code,
        "redirect_uri": settings.SLACK_REDIRECT_URI
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, data=data)
            token_data = response.json()
            
            logger.debug(f"Token exchange response: {token_data}")
            return token_data
            
    except Exception as e:
        logger.error(f"HTTP error during token exchange: {str(e)}")
        return {"ok": False, "error": str(e)}

def _redirect_to_frontend_with_slack_success(user: User, slack_connection) -> RedirectResponse:
    """Redirect to frontend with successful Slack connection data"""
    
    frontend_base_url = getattr(settings, 'FRONTEND_BASE_URL', 'http://localhost:3000')
    
    # Create success query parameters
    query_params = {
        'slack_success': 'true',
        'slack_connected': 'true',
        'slack_team': slack_connection.team_name or 'Unknown',
        'slack_user_id': slack_connection.slack_user_id,
        'message': 'Slack connected successfully',
        'timestamp': str(int(datetime.utcnow().timestamp()))
    }
    
    # Redirect to onboarding page with success parameters
    redirect_url = f"{frontend_base_url}/onboarding?{urlencode(query_params)}"
    
    logger.info(f"🎯 Redirecting to frontend after successful Slack connection: {redirect_url}")
    
    return RedirectResponse(url=redirect_url, status_code=302)

def _redirect_to_frontend_with_error(error_message: str) -> RedirectResponse:
    """Redirect to frontend with error information"""
    
    frontend_base_url = getattr(settings, 'FRONTEND_BASE_URL', 'http://localhost:3000')
    
    # Create error query parameters
    query_params = {
        'slack_success': 'false',
        'slack_error': error_message,
        'timestamp': str(int(datetime.utcnow().timestamp()))
    }
    
    # Redirect to onboarding page with error parameters
    redirect_url = f"{frontend_base_url}/onboarding?{urlencode(query_params)}"
    
    logger.warning(f"⚠️  Redirecting to frontend with Slack error: {error_message}")
    
    return RedirectResponse(url=redirect_url, status_code=302)

# =============================================================================
# SLACK CONNECTION MANAGEMENT ENDPOINTS
# =============================================================================

@router.get("/slack/connection", response_model=SlackConnectionResponse, status_code=status.HTTP_200_OK)
async def get_slack_connection(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's Slack connection details"""
    
    slack_connection = SlackService.get_slack_connection_by_user_id(db, str(current_user.id))
    
    if not slack_connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Slack connection found"
        )
    
    return SlackConnectionResponse(
        id=str(slack_connection.id),
        user_id=str(slack_connection.user_id),
        slack_user_id=slack_connection.slack_user_id,
        slack_team_id=slack_connection.slack_team_id,
        team_name=slack_connection.team_name,
        created_at=slack_connection.created_at,
        updated_at=slack_connection.updated_at
    )

@router.delete("/slack/disconnect", status_code=status.HTTP_200_OK)
async def disconnect_slack(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Disconnect user's Slack account"""
    
    success = SlackService.delete_slack_connection(db, str(current_user.id))
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Slack connection found"
        )
    
    logger.info(f"Slack disconnected for user: {current_user.email}")
    return {"message": "Slack account disconnected successfully"}

# =============================================================================
# SLACK MESSAGING ENDPOINTS
# =============================================================================

@router.post("/slack/test", status_code=status.HTTP_200_OK)
async def test_slack_notification(
    request: SlackTestMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Send test notification to user's Slack"""
    
    result = SlackService.send_test_notification(
        db, 
        str(current_user.id), 
        request.message
    )
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to send test notification: {result['error']}"
        )
    
    logger.info(f"✅ Test Slack notification sent for user: {current_user.email}")
    return {"message": "Test notification sent successfully"}

@router.post("/slack/notify/pr", status_code=status.HTTP_200_OK)
async def send_pr_notification(
    request: SlackMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Send PR notification to user's Slack"""
    
    result = SlackService.send_pr_notification(
        db,
        str(current_user.id),
        request.repo_name,
        request.pr_title,
        request.pr_url
    )
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to send PR notification: {result['error']}"
        )
    
    logger.info(f"✅ PR notification sent for user: {current_user.email}")
    return {"message": "PR notification sent successfully"}

# =============================================================================
# HEALTH CHECK AND DEBUG ENDPOINTS
# =============================================================================

@router.get("/slack/health", status_code=status.HTTP_200_OK)
async def slack_health_check():
    """Health check for Slack integration"""
    return {
        "status": "healthy",
        "service": "slack_integration",
        "slack_configured": bool(settings.SLACK_CLIENT_ID and settings.SLACK_CLIENT_SECRET),
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/slack/debug", status_code=status.HTTP_200_OK)
async def debug_slack_config():
    """Debug endpoint to check Slack OAuth configuration (development only)"""
    
    if settings.ENVIRONMENT == "production":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Debug endpoint not available in production"
        )
    
    return {
        "slack_client_id": settings.SLACK_CLIENT_ID[:10] + "..." if settings.SLACK_CLIENT_ID else None,
        "slack_client_secret_configured": bool(settings.SLACK_CLIENT_SECRET),
        "slack_redirect_uri": settings.SLACK_REDIRECT_URI,
        "frontend_base_url": getattr(settings, 'FRONTEND_BASE_URL', 'Not set'),
        "environment": settings.ENVIRONMENT,
        "oauth_configured": bool(oauth.slack),
        "required_scopes": ["chat:write", "users:read"]
    }