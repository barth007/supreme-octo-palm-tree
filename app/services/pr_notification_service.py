#====================================================================
#app/services/pr_notification_service.py
#====================================================================
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import or_
from datetime import datetime
from app.models .pr_notification import  PullRequestNotification
from app.models.user import User
from app.services.pr_perser_service import PRParserService
from app.schemas.email import  PostmarkInboundWebhook, PRExtractionResult
from typing import Annotated
from app.core.logger import get_module_logger

logger = get_module_logger(__name__, "logs/pr_notification_service.log")

class PRNotificationService:
    """
        Service for handling PR notification operations
    """
    @staticmethod
    def find_user_by_email(db: Session, email: str)-> Optional[User]:
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
            create a new PR notification record
            Args:
                db: SQLAlchemy session
                webhook_data: Postmark inbound webhook data
                extracted_data: Extracted PR data
                user: User object associated with the PR
                Returns:
                    PullRequestNotification: The created notification object
        """
        try:
            #let's check if the notification already exists
            try:
                existing_notification = db.query(PullRequestNotification).filter(
                    PullRequestNotification.message_id == webhook_data.MessageID
                ).first()
                if existing_notification:
                    logger.info(f"Notification already exists for message ID: {webhook_data.MessageID}")
                    return existing_notification
            except Exception as e:
                logger.error(f"Error checking existing notification: {str(e)}")
                raise e
            received_at = PRParserService.parse_date(webhook_data.Date)
            sender_email = (
                extracted_data.original_sender
                if extracted_data.is_forwarded and extracted_data.original_sender
                else webhook_data.From
            )
            recipient_email = PRParserService.extract_recipient_email(webhook_data)
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
                slack_sent=False,
                pr_number=extracted_data.pr_number,
                pr_status=extracted_data.pr_status,
                is_forwarded=extracted_data.is_forwarded
            )
            db.add(notification)
            db.commit()
            db.refresh(notification)
            logger.info(f"PR notification created for PR: {extracted_data.pr_title}")
            return notification
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating PR notification: {str(e)}")
            raise e
    
    @staticmethod
    def get_user_notifications(
        db: Session,
        user_id: str,
        limit: int = 100,
        repo_filter: Optional[str] = None
    )-> List[PullRequestNotification]:
        """"
            Get user notifications with optional repo filter
            Args:
                db: SQLAlchemy session
                user_id: ID of the user
                limit: Maximum number of notifications to return
                repo_filter: Optional repository name to filter notifications
            Returns:
                List[PullRequestNotification]: List of notifications for the user
        """
        try:
           if user_id is None:
                logger.warning("User ID is None, returning empty list")
                return []
           query = db.query(PullRequestNotification).filter(PullRequestNotification.user_id == user_id)
           if repo_filter:
                query = query.filter(PullRequestNotification.repo_name == repo_filter)

           return query.order_by(PullRequestNotification.received_at.desc()).limit(limit).all()
        except Exception as e:
            logger.error(f"Error retrieving user notifications: {str(e)}")
            return []
        
    @staticmethod
    def mark_slack_sent(
        db: Session,
        notification_id: str
    )-> bool:
        """"
            Mark a notifiation as sent to Slack
            Args:
                db: SQLAlchemy session
                notification_id: ID of the notification to update
            Returns:
                bool: True if the update was successful, False otherwise
        """
        try:
            notification = db.query(PullRequestNotification).filter(
                PullRequestNotification.id == notification_id
            ).first()
            if not notification:
                logger.warning(f"Notification with ID {notification_id} not found")
                return False
            notification.slack_sent = True
            db.commit()
            return True
        except Exception as e:
            logger.error(f"Error marking notification as sent to Slack: {str(e)}")
            db.rollback()
            return False
    
    @staticmethod
    def get_unsent_slack_notification(
        db: Session,
        limit: int = 10
    )-> List[PullRequestNotification]:
        """
            Get notifications that have not been sent to Slack
        """
        try:
            notification = db.query(PullRequestNotification).filter(
                PullRequestNotification.slack_sent == False
            ).order_by(
                PullRequestNotification.received_at.desc()
            ).limit(limit).all()
            if not notification:
                logger.info("No unsent Slack notifications found")
                return []
            logger.info(f"Found {len(notification)} unsent Slack notifications")
            return notification
        except Exception as e:
            logger.error(f"Error retrieving unsent Slack notifications: {str(e)}")
            return []
    
    @staticmethod
    def get_notification_stats(
        db: Session,
        user_id: Optional[str] = None,
    )-> dict:
        """
        Get notification statistics for a user
        Args:
            db: SQLAlchemy session
            user_id: ID of the user to get stats for, if None, get stats for all users
        Returns:
            dict: Dictionary containing notification counts and other stats
        """
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
