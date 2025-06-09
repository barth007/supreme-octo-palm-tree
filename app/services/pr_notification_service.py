# app/services/pr_notification_service.py (FIXED with direct Slack integration)
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import or_
from datetime import datetime
from app.models.pr_notification import PullRequestNotification
from app.models.user import User
from app.services.pr_perser_service import PRParserService
from app.services.slack_notification_service import SlackNotificationService
from app.schemas.email import PostmarkInboundWebhook, PRExtractionResult
from app.core.logger import get_module_logger

logger = get_module_logger(__name__, "logs/pr_notification_service.log")

class PRNotificationService:
    """
    Service for handling PR notification operations with automatic Slack integration
    """
    
    @staticmethod
    def find_user_by_email(db: Session, email: str) -> Optional[User]:
        """
        Find user by either their main email or inbound email
        """
        try:
            user = db.query(User).filter(
                or_(
                    User.email == email,
                    User.inbound_email == email
                )
            ).first()
            if user:
                logger.info(f"User found by email: {email}")
                return user
            else:
                logger.warning(f"No user found with email: {email}")
                return None
        except Exception as e:
            logger.error(f"Error finding user by email {email}: {str(e)}")
            return None
    
    @staticmethod
    def create_pr_notification(
        db: Session,
        webhook_data: PostmarkInboundWebhook,
        extracted_data: PRExtractionResult,
        user: User
    ) -> PullRequestNotification:
        """
        Create a new PR notification record and automatically trigger Slack notification
        """
        try:
            logger.info(f"🔥 Creating PR notification for user: {user.email}")
            
            # Check if notification already exists
            existing_notification = db.query(PullRequestNotification).filter(
                PullRequestNotification.message_id == webhook_data.MessageID
            ).first()
            
            if existing_notification:
                logger.info(f"Notification already exists for message ID: {webhook_data.MessageID}")
                return existing_notification
            
            # Parse received date
            received_at = PRParserService.parse_date(webhook_data.Date)
            
            # Determine sender email (handle forwarded emails)
            sender_email = (
                extracted_data.original_sender
                if extracted_data.is_forwarded and extracted_data.original_sender
                else webhook_data.From
            )
            
            # Extract recipient email
            recipient_email = PRParserService.extract_recipient_email(webhook_data)
            
            # Create notification record
            notification = PullRequestNotification(
                user_id=user.id,
                sender_email=sender_email,
                recipient_email=recipient_email,
                repo_name=extracted_data.repo_name,
                pr_title=extracted_data.pr_title,
                pr_link=extracted_data.pr_link,
                subject=webhook_data.Subject,
                received_at=received_at,
                message_id=webhook_data.MessageID,
                raw_text=webhook_data.TextBody,
                raw_html=webhook_data.HtmlBody,
                slack_sent=False,  # Initially false
                pr_number=extracted_data.pr_number,
                pr_status=extracted_data.pr_status,
                is_forwarded=extracted_data.is_forwarded
            )
            
            # Save to database FIRST
            db.add(notification)
            db.commit()
            db.refresh(notification)
            
            logger.info(f"✅ PR notification created in database: {notification.id}")
            logger.info(f"   PR Title: {extracted_data.pr_title}")
            logger.info(f"   Repository: {extracted_data.repo_name}")
            logger.info(f"   User: {user.email}")
            
            # 🔥 DIRECTLY SEND SLACK NOTIFICATION HERE
            slack_sent = False
            try:
                logger.info(f"🚀 ATTEMPTING TO SEND SLACK NOTIFICATION...")
                logger.info(f"   User has Slack connection: {user.slack_connection is not None}")
                
                if user.slack_connection:
                    logger.info(f"   Slack Team: {user.slack_connection.team_name}")
                    logger.info(f"   Slack User ID: {user.slack_connection.slack_user_id}")
                    
                    # Send the notification using the existing service
                    slack_result = SlackNotificationService.send_pr_reminder_notification(
                        access_token=user.slack_connection.access_token,
                        slack_user_id=user.slack_connection.slack_user_id,
                        user_name=user.name,
                        pr_notification=notification
                    )
                    
                    logger.info(f"🔔 Slack API Response: {slack_result}")
                    
                    if slack_result.get("success"):
                        # Mark as sent in database
                        notification.slack_sent = True
                        db.commit()
                        slack_sent = True
                        
                        logger.info(f"🎉 SLACK NOTIFICATION SENT SUCCESSFULLY!")
                        logger.info(f"   Message TS: {slack_result.get('data', {}).get('ts', 'N/A')}")
                    else:
                        error_msg = slack_result.get("error", "Unknown error")
                        logger.error(f"❌ SLACK NOTIFICATION FAILED: {error_msg}")
                        
                else:
                    logger.warning(f"⚠️ User {user.email} does not have Slack connected")
                    
            except Exception as slack_error:
                logger.error(f"💥 EXCEPTION SENDING SLACK NOTIFICATION: {str(slack_error)}")
                import traceback
                logger.error(f"   Full traceback: {traceback.format_exc()}")
            
            # Log final status
            if slack_sent:
                logger.info(f"✅ NOTIFICATION COMPLETE: Database saved ✅, Slack sent ✅")
            else:
                logger.warning(f"⚠️ NOTIFICATION PARTIAL: Database saved ✅, Slack failed ❌")
            
            return notification
            
        except Exception as e:
            db.rollback()
            logger.error(f"💥 ERROR CREATING PR NOTIFICATION: {str(e)}")
            import traceback
            logger.error(f"   Full traceback: {traceback.format_exc()}")
            raise e
    
    @staticmethod
    def get_user_notifications(
        db: Session,
        user_id: str,
        limit: int = 100,
        repo_filter: Optional[str] = None
    ) -> List[PullRequestNotification]:
        """Get user notifications with optional repo filter"""
        try:
            if user_id is None:
                logger.warning("User ID is None, returning empty list")
                return []
            
            query = db.query(PullRequestNotification).filter(
                PullRequestNotification.user_id == user_id
            )
            
            if repo_filter:
                query = query.filter(PullRequestNotification.repo_name == repo_filter)

            return query.order_by(
                PullRequestNotification.received_at.desc()
            ).limit(limit).all()
            
        except Exception as e:
            logger.error(f"Error retrieving user notifications: {str(e)}")
            return []
        
    @staticmethod
    def mark_slack_sent(db: Session, notification_id: str) -> bool:
        """Mark a notification as sent to Slack"""
        try:
            notification = db.query(PullRequestNotification).filter(
                PullRequestNotification.id == notification_id
            ).first()
            
            if not notification:
                logger.warning(f"Notification with ID {notification_id} not found")
                return False
            
            notification.slack_sent = True
            db.commit()
            logger.info(f"✅ Marked notification {notification_id} as sent to Slack")
            return True
            
        except Exception as e:
            logger.error(f"Error marking notification as sent to Slack: {str(e)}")
            db.rollback()
            return False
    
    @staticmethod
    def get_unsent_slack_notifications(db: Session, limit: int = 10) -> List[PullRequestNotification]:
        """Get notifications that have not been sent to Slack"""
        try:
            notifications = db.query(PullRequestNotification).filter(
                PullRequestNotification.slack_sent == False
            ).order_by(
                PullRequestNotification.received_at.desc()
            ).limit(limit).all()
            
            if not notifications:
                logger.info("No unsent Slack notifications found")
                return []
            
            logger.info(f"Found {len(notifications)} unsent Slack notifications")
            return notifications
            
        except Exception as e:
            logger.error(f"Error retrieving unsent Slack notifications: {str(e)}")
            return []
    
    @staticmethod
    def get_notification_stats(db: Session, user_id: Optional[str] = None) -> dict:
        """Get notification statistics"""
        try:
            query = db.query(PullRequestNotification)
            if user_id:
                query = query.filter(PullRequestNotification.user_id == user_id)
            
            total_notifications = query.count()
            sent_notifications = query.filter(PullRequestNotification.slack_sent == True).count()
            unsent_notifications = total_notifications - sent_notifications
            
            # Count by status
            opened = query.filter(PullRequestNotification.pr_status == 'opened').count()
            merged = query.filter(PullRequestNotification.pr_status == 'merged').count()
            closed = query.filter(PullRequestNotification.pr_status == 'closed').count()
            
            # Count forwarded emails
            forwarded = query.filter(PullRequestNotification.is_forwarded == True).count()
        
            stats = {
                'total_notifications': total_notifications,
                'slack_sent': sent_notifications,
                'pending_slack': unsent_notifications,
                'by_status': {
                    'opened': opened,
                    'merged': merged,
                    'closed': closed
                },
                'forwarded_emails': forwarded
            }
            
            logger.info(f"Notification stats: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Error retrieving notification stats: {str(e)}")
            return {}
    
    @staticmethod
    def delete_notification(db: Session, notification_id: str, user_id: str) -> bool:
        """Delete a notification (only by owner)"""
        try:
            notification = db.query(PullRequestNotification).filter(
                PullRequestNotification.id == notification_id,
                PullRequestNotification.user_id == user_id
            ).first()
            
            if notification:
                db.delete(notification)
                db.commit()
                logger.info(f"Deleted notification: {notification_id}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error deleting notification: {str(e)}")
            db.rollback()
            return False

    # 🔥 NEW: Manual retry method for testing
    @staticmethod
    def retry_slack_notification(db: Session, notification_id: str) -> bool:
        """Manually retry sending a Slack notification"""
        try:
            logger.info(f"🔄 MANUALLY RETRYING Slack notification: {notification_id}")
            
            # Get notification with user
            notification = db.query(PullRequestNotification).filter(
                PullRequestNotification.id == notification_id
            ).first()
            
            if not notification:
                logger.error(f"❌ Notification not found: {notification_id}")
                return False
            
            # Get user
            user = db.query(User).filter(User.id == notification.user_id).first()
            if not user:
                logger.error(f"❌ User not found for notification: {notification_id}")
                return False
            
            if not user.slack_connection:
                logger.error(f"❌ User {user.email} has no Slack connection")
                return False
            
            # Send notification
            slack_result = SlackNotificationService.send_pr_reminder_notification(
                access_token=user.slack_connection.access_token,
                slack_user_id=user.slack_connection.slack_user_id,
                user_name=user.name,
                pr_notification=notification
            )
            
            if slack_result.get("success"):
                notification.slack_sent = True
                db.commit()
                logger.info(f"✅ RETRY SUCCESSFUL for notification: {notification_id}")
                return True
            else:
                logger.error(f"❌ RETRY FAILED: {slack_result.get('error')}")
                return False
                
        except Exception as e:
            logger.error(f"💥 Exception in retry_slack_notification: {str(e)}")
            return False