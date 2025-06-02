# =============================================================================
# app/services/slack_service.py
# =============================================================================
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
import requests
from app.models.slack_connection import SlackConnection
from app.models.user import User
from app.schemas.slack import SlackConnectionCreate
from app.core.logger import get_module_logger

logger = get_module_logger(__name__, "logs/slack_service.log")

class SlackService:
    """Service for handling Slack operations"""
    
    @staticmethod
    def get_slack_connection_by_user_id(db: Session, user_id: str) -> Optional[SlackConnection]:
        """Get Slack connection by user ID"""
        return db.query(SlackConnection).filter(SlackConnection.user_id == user_id).first()
    
    @staticmethod
    def create_slack_connection(db: Session, user_id: str, slack_data: SlackConnectionCreate) -> SlackConnection:
        """Create or update Slack connection"""
        # Check if connection already exists
        existing_connection = SlackService.get_slack_connection_by_user_id(db, user_id)
        
        if existing_connection:
            # Update existing connection
            existing_connection.slack_user_id = slack_data.slack_user_id
            existing_connection.slack_team_id = slack_data.slack_team_id
            existing_connection.access_token = slack_data.access_token
            existing_connection.team_name = slack_data.team_name
            db.commit()
            db.refresh(existing_connection)
            logger.info(f"Updated Slack connection for user: {user_id}")
            return existing_connection
        else:
            # Create new connection
            slack_connection = SlackConnection(
                user_id=user_id,
                **slack_data.model_dump()
            )
            db.add(slack_connection)
            db.commit()
            db.refresh(slack_connection)
            logger.info(f"Created Slack connection for user: {user_id}")
            return slack_connection
    
    @staticmethod
    def delete_slack_connection(db: Session, user_id: str) -> bool:
        """Delete Slack connection"""
        connection = SlackService.get_slack_connection_by_user_id(db, user_id)
        if connection:
            db.delete(connection)
            db.commit()
            logger.info(f"Deleted Slack connection for user: {user_id}")
            return True
        return False
    
    @staticmethod
    def send_slack_message(access_token: str, channel: str, message: str) -> Dict[str, Any]:
        """Send message to Slack channel"""
        url = "https://slack.com/api/chat.postMessage"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "channel": channel,
            "text": message
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload)
            response_data = response.json()
            
            if response_data.get("ok"):
                logger.info(f"Successfully sent Slack message to channel: {channel}")
                return {"success": True, "data": response_data}
            else:
                logger.error(f"Failed to send Slack message: {response_data.get('error', 'Unknown error')}")
                return {"success": False, "error": response_data.get("error", "Unknown error")}
                
        except Exception as e:
            logger.error(f"Exception while sending Slack message: {str(e)}")
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def send_pr_notification(db: Session, user_id: str, repo_name: str, pr_title: str, pr_url: str) -> Dict[str, Any]:
        """Send PR notification to user's Slack"""
        slack_connection = SlackService.get_slack_connection_by_user_id(db, user_id)
        
        if not slack_connection:
            return {"success": False, "error": "No Slack connection found for user"}
        
        message = f"""🔔 You have a pending PR to review:

• **Repo:** {repo_name}
• **Title:** {pr_title}
• **Link:** <{pr_url}|View PR>

Click the link above to review the pull request."""
        
        # Send to the user's Slack DM (using their Slack user ID as channel)
        return SlackService.send_slack_message(
            access_token=slack_connection.access_token,
            channel=slack_connection.slack_user_id,
            message=message
        )
    
    @staticmethod
    def send_test_notification(db: Session, user_id: str, message: str = None) -> Dict[str, Any]:
        """Send test notification to user's Slack"""
        slack_connection = SlackService.get_slack_connection_by_user_id(db, user_id)
        
        if not slack_connection:
            return {"success": False, "error": "No Slack connection found for user"}
        
        test_message = message or "🚀 Test notification from your FastAPI app! Your Slack integration is working perfectly."
        
        return SlackService.send_slack_message(
            access_token=slack_connection.access_token,
            channel=slack_connection.slack_user_id,
            message=test_message
        )