# =============================================================================
# app/api/v1/endpoints/slack_auth.py
# =============================================================================
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services.slack_service import SlackService
from app.schemas.slack import SlackConnectionCreate, SlackConnectionResponse, SlackTestMessageRequest, SlackMessageRequest
from app.utils.oauth import oauth
from app.core.config import settings
from app.core.logger import get_module_logger

logger = get_module_logger(__name__, "logs/slack_auth.log")

router = APIRouter()

@router.get("/slack/login", status_code=status.HTTP_302_FOUND)
async def slack_login(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Initiate Slack OAuth2 login"""
    if not settings.SLACK_CLIENT_ID or not settings.SLACK_CLIENT_SECRET:
        logger.error("Slack OAuth2 credentials are not configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Slack OAuth2 is not configured"
        )
    
    if not oauth.slack:
        logger.error("Slack OAuth2 client is not configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Slack OAuth2 client is not configured"
        )
    
    redirect_uri = settings.SLACK_REDIRECT_URI
    logger.info(f"Initiating Slack OAuth for user: {current_user.email}")
    logger.debug(f"Redirect URI: {redirect_uri}")
    
    # Add user ID to state for security
    state = f"user_{current_user.id}"
    
    return await oauth.slack.authorize_redirect(
        request, 
        redirect_uri,
        state=state
    )

@router.get("/slack/callback", response_model=SlackConnectionResponse, status_code=status.HTTP_200_OK)
async def slack_callback(
    request: Request,
    db: Session = Depends(get_db)
):
    """Handle Slack OAuth2 callback"""
    try:
        # Get the token from Slack
        token = await oauth.slack.authorize_access_token(request)
        if not token:
            logger.error("Failed to retrieve token from Slack")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to retrieve token from Slack"
            )
        
        logger.info("Successfully retrieved token from Slack")
        logger.debug(f"Token response: {token}")
        
        if "error" in token:
            logger.error(f"Error in Slack token response: {token['error']}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Slack OAuth error: {token['error']}"
            )
        
        # Extract user ID from state
        state = request.query_params.get("state")
        if not state or not state.startswith("user_"):
            logger.error("Invalid or missing state parameter")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid state parameter"
            )
        
        user_id = state.replace("user_", "")
        
        # Verify user exists
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.error(f"User not found: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Extract Slack data
        access_token = token.get("access_token")
        authed_user = token.get("authed_user", {})
        team = token.get("team", {})
        
        slack_user_id = authed_user.get("id")
        slack_team_id = team.get("id")
        team_name = team.get("name")
        
        if not slack_user_id or not slack_team_id:
            logger.error("Missing required Slack user or team information")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing required Slack information"
            )
        
        # Create Slack connection
        slack_data = SlackConnectionCreate(
            slack_user_id=slack_user_id,
            slack_team_id=slack_team_id,
            access_token=access_token,
            team_name=team_name
        )
        
        slack_connection = SlackService.create_slack_connection(db, user_id, slack_data)
        
        return SlackConnectionResponse(
            id=str(slack_connection.id),
            user_id=str(slack_connection.user_id),
            slack_user_id=slack_connection.slack_user_id,
            slack_team_id=slack_connection.slack_team_id,
            team_name=slack_connection.team_name,
            created_at=slack_connection.created_at,
            updated_at=slack_connection.updated_at
        )
        
    except Exception as e:
        logger.error(f"Slack OAuth callback failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Slack authentication failed: {str(e)}"
        )

@router.delete("/slack/disconnect", status_code=status.HTTP_200_OK)
async def disconnect_slack(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Disconnect Slack account"""
    success = SlackService.delete_slack_connection(db, str(current_user.id))
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Slack connection found"
        )
    
    logger.info(f"Slack disconnected for user: {current_user.email}")
    return {"message": "Slack account disconnected successfully"}

@router.post("/slack/test", status_code=status.HTTP_200_OK)
async def test_slack_notification(
    request: SlackTestMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Send test notification to Slack"""
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
    
    logger.info(f"Test Slack notification sent for user: {current_user.email}")
    return {"message": "Test notification sent successfully"}

@router.post("/slack/notify/pr", status_code=status.HTTP_200_OK)
async def send_pr_notification(
    request: SlackMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Send PR notification to Slack"""
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
    
    logger.info(f"PR notification sent for user: {current_user.email}")
    return {"message": "PR notification sent successfully"}