# =============================================================================
# app/api/v1/endpoints/users.py
# =============================================================================
from fastapi import APIRouter, Depends
from app.schemas.user import UserResponse
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services.user_service import UserService
from app.schemas.slack import SlackConnectionResponse
from app.db.session import get_db
from app.core.logger import get_module_logger
from sqlalchemy.orm import Session


logger = get_module_logger(__name__, "logs/users.log")


router = APIRouter()

@router.get("/me", response_model=UserResponse, status_code=200)
async def get_current_user_info(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get current user information"""
    logger.info(f"Fetching information for user: {current_user.email}")
    # Get user with Slack connection details
    user_with_slack = UserService.get_user_by_id(db, str(current_user.id))
    
    slack_connection_data = None
    if user_with_slack and user_with_slack.slack_connection:
        slack_connection_data = SlackConnectionResponse(
            id=str(user_with_slack.slack_connection.id),
            user_id=str(user_with_slack.slack_connection.user_id),
            slack_user_id=user_with_slack.slack_connection.slack_user_id,
            slack_team_id=user_with_slack.slack_connection.slack_team_id,
            team_name=user_with_slack.slack_connection.team_name,
            created_at=user_with_slack.slack_connection.created_at,
            updated_at=user_with_slack.slack_connection.updated_at
        )
    return UserResponse(
        id=str(current_user.id),
        name=current_user.name,
        email=current_user.email,
        profile_image=current_user.profile_image,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
        slack_connection=slack_connection_data
    )