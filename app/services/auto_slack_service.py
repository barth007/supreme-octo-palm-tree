# app/services/auto_slack_service.py (NEW)
import asyncio
from typing import Optional
from sqlalchemy.orm import Session
from app.models.pr_notification import PullRequestNotification
from app.models.user import User
from app.services.slack_notification_service import SlackNotificationService
from app.core.logger import get_module_logger

logger = get_module_logger(__name__, "logs/auto_slack_service.log")

class AutoSlackService:
    """Service for automatically sending Slack notifications when PR notifications are created"""
    
    @staticmethod
    def trigger_slack_notification(db: Session, notification_id: str) -> bool:
        """
        Automatically trigger Slack notification for a newly created PR notification
        
        Args:
            db: Database session
            notification_id: ID of the newly created notification
            
        Returns:
            bool: True if notification was sent successfully, False otherwise
        """
        try:
            logger.info(f"🔔 Triggering auto Slack notification for: {notification_id}")
            
            # Get the notification with user and slack connection
            notification = db.query(PullRequestNotification).filter(
                PullRequestNotification.id == notification_id
            ).first()
            
            if not notification:
                logger.error(f"❌ Notification not found: {notification_id}")
                return False
            
            # Get user with Slack connection
            user = db.query(User).filter(User.id == notification.user_id).first()
            if not user:
                logger.error(f"❌ User not found for notification: {notification_id}")
                return False
            
            # Check if user has Slack connection
            if not user.slack_connection:
                logger.info(f"⚠️ User {user.email} does not have Slack connected - skipping notification")
                return False
            
            # Check if already sent to avoid duplicates
            if notification.slack_sent:
                logger.info(f"ℹ️ Notification {notification_id} already sent to Slack - skipping")
                return True
            
            logger.info(f"📤 Sending Slack notification to {user.email} (Team: {user.slack_connection.team_name})")
            
            # Send the Slack notification
            result = SlackNotificationService.send_pr_reminder_notification(
                access_token=user.slack_connection.access_token,
                slack_user_id=user.slack_connection.slack_user_id,
                user_name=user.name,
                pr_notification=notification
            )
            
            if result.get("success"):
                # Mark as sent in database
                notification.slack_sent = True
                db.commit()
                
                logger.info(f"✅ Slack notification sent successfully for PR: {notification.pr_title}")
                logger.info(f"   Repository: {notification.repo_name}")
                logger.info(f"   User: {user.email}")
                return True
            else:
                error_msg = result.get("error", "Unknown error")
                logger.error(f"❌ Failed to send Slack notification: {error_msg}")
                return False
                
        except Exception as e:
            logger.error(f"💥 Exception in trigger_slack_notification: {str(e)}")
            db.rollback()
            return False
    
    @staticmethod
    async def process_pending_notifications(db: Session, limit: int = 10) -> dict:
        """
        Process pending notifications that haven't been sent to Slack yet
        
        Args:
            db: Database session
            limit: Maximum number of notifications to process
            
        Returns:
            dict: Processing results
        """
        try:
            logger.info(f"🔄 Processing up to {limit} pending Slack notifications...")
            
            # Get pending notifications (not sent to Slack yet)
            pending_notifications = db.query(PullRequestNotification).filter(
                PullRequestNotification.slack_sent == False
            ).order_by(
                PullRequestNotification.created_at.asc()  # Oldest first
            ).limit(limit).all()
            
            if not pending_notifications:
                logger.info("ℹ️ No pending notifications found")
                return {"processed": 0, "sent": 0, "failed": 0}
            
            logger.info(f"📋 Found {len(pending_notifications)} pending notifications")
            
            sent_count = 0
            failed_count = 0
            
            for notification in pending_notifications:
                success = AutoSlackService.trigger_slack_notification(db, str(notification.id))
                if success:
                    sent_count += 1
                else:
                    failed_count += 1
                
                # Small delay between notifications to avoid rate limiting
                await asyncio.sleep(0.5)
            
            result = {
                "processed": len(pending_notifications),
                "sent": sent_count,
                "failed": failed_count
            }
            
            logger.info(f"✅ Processed {len(pending_notifications)} notifications: {sent_count} sent, {failed_count} failed")
            return result
            
        except Exception as e:
            logger.error(f"💥 Error processing pending notifications: {str(e)}")
            return {"processed": 0, "sent": 0, "failed": 0, "error": str(e)}