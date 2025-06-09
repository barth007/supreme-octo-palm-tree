# app/api/v1/endpoints/slack_retry.py (NEW)
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services.auto_slack_service import AutoSlackService
from app.services.pr_notification_service import PRNotificationService
from app.core.logger import get_module_logger

logger = get_module_logger(__name__, "logs/slack_retry.log")

router = APIRouter()

@router.post("/retry-pending", status_code=status.HTTP_200_OK)
async def retry_pending_slack_notifications(
    limit: int = Query(10, ge=1, le=50, description="Maximum notifications to process"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retry sending Slack notifications for pending notifications
    Can be triggered manually by users or automatically by system
    """
    try:
        logger.info(f"Retry pending Slack notifications requested by {current_user.email}")
        
        # Check if user has Slack connection
        if not current_user.slack_connection:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No Slack connection found. Please connect your Slack account first."
            )
        
        # Get user's pending notifications
        pending_notifications = PRNotificationService.get_unsent_slack_notifications(db, limit)
        
        if not pending_notifications:
            return {
                "message": "No pending Slack notifications found",
                "processed": 0,
                "sent": 0,
                "failed": 0
            }
        
        logger.info(f"Found {len(pending_notifications)} pending notifications for retry")
        
        # Process notifications in background
        background_tasks.add_task(
            process_notifications_background,
            db,
            [str(n.id) for n in pending_notifications]
        )
        
        return {
            "message": f"Processing {len(pending_notifications)} pending notifications in background",
            "processed": len(pending_notifications),
            "status": "processing"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in retry_pending_slack_notifications: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing retry request: {str(e)}"
        )

@router.post("/retry-notification/{notification_id}", status_code=status.HTTP_200_OK)
async def retry_single_notification(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retry sending Slack notification for a specific notification
    """
    try:
        logger.info(f"Retry single notification {notification_id} requested by {current_user.email}")
        
        # Check if user has Slack connection
        if not current_user.slack_connection:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No Slack connection found. Please connect your Slack account first."
            )
        
        # Trigger Slack notification
        success = AutoSlackService.trigger_slack_notification(db, notification_id)
        
        if success:
            return {
                "message": "Slack notification sent successfully",
                "success": True,
                "notification_id": notification_id
            }
        else:
            return {
                "message": "Failed to send Slack notification",
                "success": False,
                "notification_id": notification_id
            }
            
    except Exception as e:
        logger.error(f"Error retrying notification {notification_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrying notification: {str(e)}"
        )

@router.get("/pending-count", status_code=status.HTTP_200_OK)
async def get_pending_slack_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get count of pending Slack notifications for current user
    """
    try:
        from app.models.pr_notification import PullRequestNotification
        from sqlalchemy import and_
        
        pending_count = db.query(PullRequestNotification).filter(
            and_(
                PullRequestNotification.user_id == current_user.id,
                PullRequestNotification.slack_sent == False
            )
        ).count()
        
        return {
            "pending_count": pending_count,
            "user_email": current_user.email,
            "slack_connected": bool(current_user.slack_connection)
        }
        
    except Exception as e:
        logger.error(f"Error getting pending count: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting pending count: {str(e)}"
        )

@router.get("/slack-status", status_code=status.HTTP_200_OK)
async def get_slack_notification_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed Slack notification status for current user
    """
    try:
        stats = PRNotificationService.get_notification_stats(db, str(current_user.id))
        
        return {
            "user_email": current_user.email,
            "slack_connected": bool(current_user.slack_connection),
            "slack_team": current_user.slack_connection.team_name if current_user.slack_connection else None,
            "total_notifications": stats.get('total_notifications', 0),
            "slack_sent": stats.get('slack_sent', 0),
            "pending_slack": stats.get('pending_slack', 0),
            "auto_send_enabled": True  # Always enabled in this implementation
        }
        
    except Exception as e:
        logger.error(f"Error getting Slack status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting Slack status: {str(e)}"
        )

async def process_notifications_background(db: Session, notification_ids: list):
    """
    Background task to process notification retries
    """
    try:
        logger.info(f"Processing {len(notification_ids)} notifications in background")
        
        sent_count = 0
        failed_count = 0
        
        for notification_id in notification_ids:
            try:
                success = AutoSlackService.trigger_slack_notification(db, notification_id)
                if success:
                    sent_count += 1
                else:
                    failed_count += 1
                    
                # Small delay to avoid rate limiting
                import asyncio
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error processing notification {notification_id}: {str(e)}")
                failed_count += 1
        
        logger.info(f"Background processing complete: {sent_count} sent, {failed_count} failed")
        
    except Exception as e:
        logger.error(f"Error in background processing: {str(e)}")
    finally:
        db.close()