# =============================================================================
# app/services/background_tasks_service.py
# =============================================================================
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from datetime import datetime, timedelta
from fastapi import BackgroundTasks
from app.models.user import User
from app.models.pr_notification import PullRequestNotification
from app.models.slack_connection import SlackConnection
from app.services.slack_notification_service import SlackNotificationService
from app.services.pr_management_service import PRManagementService
from app.core.logger import get_module_logger

logger = get_module_logger(__name__, "logs/background_tasks.log")

class PRReminderBackgroundService:
    """Service for handling background tasks related to PR reminders"""
    
    @staticmethod
    def send_pr_reminders_task(
        db: Session,
        reminder_threshold_days: int = 2,
        max_reminders_per_user: int = 10
    ):
        """
        Background task to send PR reminders to users
        """
        logger.info(f"Starting PR reminder task with {reminder_threshold_days} day threshold")
        
        try:
            # Get all users with Slack connections
            users_with_slack = db.query(User).join(SlackConnection).all()
            
            if not users_with_slack:
                logger.info("No users with Slack connections found")
                return {"processed_users": 0, "sent_reminders": 0}
            
            total_reminders_sent = 0
            processed_users = 0
            
            for user in users_with_slack:
                try:
                    # Get old open PRs for this user
                    old_prs = PRReminderBackgroundService._get_old_open_prs(
                        db, str(user.id), reminder_threshold_days
                    )
                    
                    if not old_prs:
                        logger.debug(f"No old PRs found for user {user.email}")
                        continue
                    
                    # Limit the number of reminders per user
                    prs_to_remind = old_prs[:max_reminders_per_user]
                    
                    # Send reminders
                    result = PRReminderBackgroundService._send_user_pr_reminders(
                        db, user, prs_to_remind
                    )
                    
                    if result.get("success"):
                        sent_count = result.get("sent_count", 0)
                        total_reminders_sent += sent_count
                        processed_users += 1
                        
                        # Mark PRs as having Slack notification sent
                        PRReminderBackgroundService._mark_prs_slack_sent(db, prs_to_remind)
                        
                        logger.info(f"Sent {sent_count} reminders to {user.email}")
                    else:
                        logger.error(f"Failed to send reminders to {user.email}: {result.get('error')}")
                
                except Exception as e:
                    logger.error(f"Error processing reminders for user {user.email}: {str(e)}")
                    continue
            
            logger.info(f"PR reminder task completed: {total_reminders_sent} reminders sent to {processed_users} users")
            
            return {
                "processed_users": processed_users,
                "sent_reminders": total_reminders_sent,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Error in PR reminder background task: {str(e)}")
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def send_daily_summaries_task(db: Session):
        """
        Background task to send daily PR summaries to users
        """
        logger.info("Starting daily summary task")
        
        try:
            users_with_slack = db.query(User).join(SlackConnection).all()
            processed_users = 0
            
            for user in users_with_slack:
                try:
                    # Generate daily summary data
                    summary_data = PRReminderBackgroundService._generate_daily_summary(
                        db, str(user.id)
                    )
                    
                    # Only send if there's meaningful activity
                    if summary_data.get('total_open', 0) > 0:
                        result = PRReminderBackgroundService._send_daily_summary(
                            user, summary_data
                        )
                        
                        if result.get("success"):
                            processed_users += 1
                            logger.info(f"Sent daily summary to {user.email}")
                        else:
                            logger.error(f"Failed to send daily summary to {user.email}")
                
                except Exception as e:
                    logger.error(f"Error sending daily summary to {user.email}: {str(e)}")
                    continue
            
            logger.info(f"Daily summary task completed: {processed_users} summaries sent")
            return {"processed_users": processed_users, "success": True}
            
        except Exception as e:
            logger.error(f"Error in daily summary background task: {str(e)}")
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def cleanup_old_notifications_task(
        db: Session,
        cleanup_threshold_days: int = 90
    ):
        """
        Background task to clean up old PR notifications
        """
        logger.info(f"Starting cleanup task for notifications older than {cleanup_threshold_days} days")
        
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=cleanup_threshold_days)
            
            # Delete old notifications (only merged/closed PRs)
            deleted_count = db.query(PullRequestNotification).filter(
                and_(
                    PullRequestNotification.received_at < cutoff_date,
                    or_(
                        PullRequestNotification.pr_status == 'merged',
                        PullRequestNotification.pr_status == 'closed'
                    )
                )
            ).delete()
            
            db.commit()
            
            logger.info(f"Cleanup completed: {deleted_count} old notifications removed")
            return {"deleted_count": deleted_count, "success": True}
            
        except Exception as e:
            logger.error(f"Error in cleanup background task: {str(e)}")
            db.rollback()
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def _get_old_open_prs(
        db: Session,
        user_id: str,
        threshold_days: int
    ) -> List[PullRequestNotification]:
        """
        Get open PRs older than threshold for a specific user
        """
        cutoff_date = datetime.utcnow() - timedelta(days=threshold_days)
        
        return db.query(PullRequestNotification).filter(
            and_(
                PullRequestNotification.user_id == user_id,
                PullRequestNotification.pr_status == 'opened',
                PullRequestNotification.received_at <= cutoff_date,
                PullRequestNotification.slack_sent == False  # Haven't sent reminder yet
            )
        ).order_by(PullRequestNotification.received_at.asc()).all()
    
    @staticmethod
    def _send_user_pr_reminders(
        db: Session,
        user: User,
        prs_to_remind: List[PullRequestNotification]
    ) -> Dict[str, Any]:
        """
        Send PR reminders to a specific user
        """
        try:
            slack_connection = user.slack_connection
            if not slack_connection:
                return {"success": False, "error": "No Slack connection"}
            
            # Decide whether to send individual or bulk reminders
            if len(prs_to_remind) == 1:
                # Send individual reminder
                result = SlackNotificationService.send_pr_reminder_notification(
                    access_token=slack_connection.access_token,
                    slack_user_id=slack_connection.slack_user_id,
                    user_name=user.name,
                    pr_notification=prs_to_remind[0]
                )
                
                return {
                    "success": result.get("success", False),
                    "sent_count": 1 if result.get("success") else 0,
                    "error": result.get("error")
                }
            
            else:
                # Send bulk reminder
                result = SlackNotificationService.send_bulk_pr_reminders(
                    access_token=slack_connection.access_token,
                    slack_user_id=slack_connection.slack_user_id,
                    user_name=user.name,
                    pr_notifications=prs_to_remind
                )
                
                return {
                    "success": result.get("success", False),
                    "sent_count": len(prs_to_remind) if result.get("success") else 0,
                    "error": result.get("error")
                }
        
        except Exception as e:
            logger.error(f"Error sending PR reminders to {user.email}: {str(e)}")
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def _send_daily_summary(user: User, summary_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send daily summary to a user
        """
        try:
            slack_connection = user.slack_connection
            if not slack_connection:
                return {"success": False, "error": "No Slack connection"}
            
            result = SlackNotificationService.send_daily_summary(
                access_token=slack_connection.access_token,
                slack_user_id=slack_connection.slack_user_id,
                user_name=user.name,
                summary_data=summary_data
            )
            
            return result
        
        except Exception as e:
            logger.error(f"Error sending daily summary to {user.email}: {str(e)}")
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def _generate_daily_summary(db: Session, user_id: str) -> Dict[str, Any]:
        """
        Generate daily summary data for a user
        """
        try:
            # Get current stats
            stats = PRManagementService.get_user_pr_stats(db, user_id)
            
            # Get today's new PRs
            today = datetime.utcnow().date()
            new_today = db.query(PullRequestNotification).filter(
                and_(
                    PullRequestNotification.user_id == user_id,
                    PullRequestNotification.received_at >= today
                )
            ).count()
            
            # Get PRs needing attention (old open PRs)
            old_threshold = datetime.utcnow() - timedelta(days=3)
            needs_attention = db.query(PullRequestNotification).filter(
                and_(
                    PullRequestNotification.user_id == user_id,
                    PullRequestNotification.pr_status == 'opened',
                    PullRequestNotification.received_at <= old_threshold
                )
            ).count()
            
            # Generate action items
            action_items = []
            if needs_attention > 0:
                action_items.append(f"Review {needs_attention} old open PR{'s' if needs_attention > 1 else ''}")
            
            if stats.get('pending_slack', 0) > 0:
                action_items.append(f"Check {stats.get('pending_slack')} pending notifications")
            
            if new_today > 0:
                action_items.append(f"Review {new_today} new PR{'s' if new_today > 1 else ''} from today")
            
            return {
                "total_open": stats.get('by_status', {}).get('opened', 0),
                "new_today": new_today,
                "needs_attention": needs_attention,
                "most_active_repo": stats.get('most_active_repo'),
                "action_items": action_items
            }
        
        except Exception as e:
            logger.error(f"Error generating daily summary for user {user_id}: {str(e)}")
            return {}
    
    @staticmethod
    def _mark_prs_slack_sent(db: Session, prs: List[PullRequestNotification]):
        """
        Mark PRs as having been sent to Slack
        """
        try:
            for pr in prs:
                pr.slack_sent = True
            db.commit()
            logger.debug(f"Marked {len(prs)} PRs as Slack sent")
        except Exception as e:
            logger.error(f"Error marking PRs as Slack sent: {str(e)}")
            db.rollback()


# =============================================================================
# Background Task Scheduler Functions
# =============================================================================

def schedule_pr_reminders(background_tasks: BackgroundTasks, db: Session):
    """
    Schedule PR reminder background task
    """
    background_tasks.add_task(
        PRReminderBackgroundService.send_pr_reminders_task,
        db=db,
        reminder_threshold_days=2,  # Remind about PRs older than 2 days
        max_reminders_per_user=10   # Max 10 reminders per user
    )
    logger.info("Scheduled PR reminders background task")

def schedule_daily_summaries(background_tasks: BackgroundTasks, db: Session):
    """
    Schedule daily summary background task
    """
    background_tasks.add_task(
        PRReminderBackgroundService.send_daily_summaries_task,
        db=db
    )
    logger.info("Scheduled daily summaries background task")

def schedule_cleanup_old_notifications(background_tasks: BackgroundTasks, db: Session):
    """
    Schedule cleanup background task
    """
    background_tasks.add_task(
        PRReminderBackgroundService.cleanup_old_notifications_task,
        db=db,
        cleanup_threshold_days=90  # Clean up notifications older than 90 days
    )
    logger.info("Scheduled cleanup background task")