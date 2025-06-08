# =============================================================================
# app/api/v1/endpoints/slack_reminders.py
# =============================================================================
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import Optional
from datetime import datetime, timedelta
from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.pr_notification import PullRequestNotification
from app.services.background_tasks_service import (
    PRReminderBackgroundService,
    schedule_pr_reminders,
    schedule_daily_summaries,
    schedule_cleanup_old_notifications
)
from app.services.slack_notification_service import SlackNotificationService
from app.services.pr_management_service import PRManagementService
from app.schemas.pr_management import PRFilterParams
from app.core.logger import get_module_logger

logger = get_module_logger(__name__, "logs/slack_reminders.log")

router = APIRouter()

# =============================================================================
# Manual Reminder Endpoints
# =============================================================================

@router.post("/send-my-reminders", status_code=status.HTTP_200_OK)
async def send_my_pr_reminders(
    days_threshold: int = Query(2, ge=1, le=30, description="Send reminders for PRs older than X days"),
    max_reminders: int = Query(10, ge=1, le=50, description="Maximum number of reminders to send"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Manually trigger PR reminders for the current user
    """
    logger.info(f"Manual PR reminder requested by {current_user.email} (threshold: {days_threshold} days)")
    
    # Check if user has Slack connection
    if not current_user.slack_connection:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Slack connection found. Please connect your Slack account first."
        )
    
    try:
        # Get old open PRs for the user
        cutoff_date = datetime.utcnow() - timedelta(days=days_threshold)
        
        old_prs = db.query(PullRequestNotification).filter(
            and_(
                PullRequestNotification.user_id == current_user.id,
                PullRequestNotification.pr_status == 'opened',
                PullRequestNotification.received_at <= cutoff_date
            )
        ).order_by(PullRequestNotification.received_at.asc()).limit(max_reminders).all()
        
        if not old_prs:
            return {
                "message": f"No open PRs older than {days_threshold} days found",
                "sent_count": 0
            }
        
        # Send reminders
        result = PRReminderBackgroundService._send_user_pr_reminders(
            db, current_user, old_prs
        )
        
        if result.get("success"):
            # Mark as sent to Slack
            PRReminderBackgroundService._mark_prs_slack_sent(db, old_prs)
            
            return {
                "message": f"Successfully sent {result.get('sent_count', 0)} PR reminders",
                "sent_count": result.get('sent_count', 0),
                "prs_reminded": [
                    {
                        "id": str(pr.id),
                        "repo": pr.repo_name,
                        "title": pr.pr_title,
                        "days_old": (datetime.utcnow() - pr.received_at).days
                    } for pr in old_prs
                ]
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to send reminders: {result.get('error')}"
            )
    
    except Exception as e:
        logger.error(f"Error sending manual reminders for {current_user.email}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error sending reminders: {str(e)}"
        )

@router.post("/send-daily-summary", status_code=status.HTTP_200_OK)
async def send_my_daily_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Manually trigger daily summary for the current user
    """
    logger.info(f"Manual daily summary requested by {current_user.email}")
    
    # Check if user has Slack connection
    if not current_user.slack_connection:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Slack connection found. Please connect your Slack account first."
        )
    
    try:
        # Generate summary data
        summary_data = PRReminderBackgroundService._generate_daily_summary(
            db, str(current_user.id)
        )
        
        if summary_data.get('total_open', 0) == 0:
            return {
                "message": "No active PRs found. Nothing to summarize!",
                "summary_sent": False
            }
        
        # Send summary
        result = PRReminderBackgroundService._send_daily_summary(
            current_user, summary_data
        )
        
        if result.get("success"):
            return {
                "message": "Daily summary sent successfully",
                "summary_sent": True,
                "summary_data": summary_data
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to send summary: {result.get('error')}"
            )
    
    except Exception as e:
        logger.error(f"Error sending manual summary for {current_user.email}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error sending summary: {str(e)}"
        )

@router.post("/test-slack-connection", status_code=status.HTTP_200_OK)
async def test_slack_connection(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Test the user's Slack connection by sending a test message
    """
    logger.info(f"Slack connection test requested by {current_user.email}")
    
    # Check if user has Slack connection
    if not current_user.slack_connection:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Slack connection found. Please connect your Slack account first."
        )
    
    try:
        result = SlackNotificationService.test_slack_connection(
            access_token=current_user.slack_connection.access_token,
            slack_user_id=current_user.slack_connection.slack_user_id
        )
        
        if result.get("success"):
            return {
                "message": "Slack connection test successful! Check your Slack DMs.",
                "connection_working": True,
                "slack_team": current_user.slack_connection.team_name
            }
        else:
            return {
                "message": f"Slack connection test failed: {result.get('error')}",
                "connection_working": False,
                "error": result.get('error')
            }
    
    except Exception as e:
        logger.error(f"Error testing Slack connection for {current_user.email}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error testing connection: {str(e)}"
        )

# =============================================================================
# Background Task Trigger Endpoints (Admin/System Use)
# =============================================================================

@router.post("/trigger-all-reminders", status_code=status.HTTP_202_ACCEPTED)
async def trigger_all_pr_reminders(
    background_tasks: BackgroundTasks,
    days_threshold: int = Query(2, ge=1, le=30, description="Remind about PRs older than X days"),
    max_per_user: int = Query(10, ge=1, le=50, description="Max reminders per user"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)  # You might want to add admin check here
):
    """
    Trigger PR reminders for all users (background task)
    This runs asynchronously and returns immediately
    """
    logger.info(f"All-users PR reminder triggered by {current_user.email}")
    
    # Schedule the background task
    background_tasks.add_task(
        PRReminderBackgroundService.send_pr_reminders_task,
        db=db,
        reminder_threshold_days=days_threshold,
        max_reminders_per_user=max_per_user
    )
    
    return {
        "message": "PR reminder task scheduled for all users",
        "status": "processing",
        "threshold_days": days_threshold,
        "max_per_user": max_per_user
    }

@router.post("/trigger-daily-summaries", status_code=status.HTTP_202_ACCEPTED)
async def trigger_all_daily_summaries(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)  # You might want to add admin check here
):
    """
    Trigger daily summaries for all users (background task)
    """
    logger.info(f"All-users daily summary triggered by {current_user.email}")
    
    # Schedule the background task
    background_tasks.add_task(
        PRReminderBackgroundService.send_daily_summaries_task,
        db=db
    )
    
    return {
        "message": "Daily summary task scheduled for all users",
        "status": "processing"
    }

@router.post("/trigger-cleanup", status_code=status.HTTP_202_ACCEPTED)
async def trigger_cleanup_old_notifications(
    background_tasks: BackgroundTasks,
    cleanup_days: int = Query(90, ge=30, le=365, description="Delete notifications older than X days"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)  # You might want to add admin check here
):
    """
    Trigger cleanup of old notifications (background task)
    """
    logger.info(f"Cleanup task triggered by {current_user.email} (threshold: {cleanup_days} days)")
    
    # Schedule the background task
    background_tasks.add_task(
        PRReminderBackgroundService.cleanup_old_notifications_task,
        db=db,
        cleanup_threshold_days=cleanup_days
    )
    
    return {
        "message": f"Cleanup task scheduled for notifications older than {cleanup_days} days",
        "status": "processing",
        "cleanup_threshold": cleanup_days
    }

# =============================================================================
# Reminder Settings & Status Endpoints
# =============================================================================

@router.get("/reminder-preview", status_code=status.HTTP_200_OK)
async def get_reminder_preview(
    days_threshold: int = Query(2, ge=1, le=30, description="Preview PRs older than X days"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Preview what PRs would be included in reminders
    """
    logger.info(f"Reminder preview requested by {current_user.email} (threshold: {days_threshold} days)")
    
    try:
        # Get old open PRs that would be reminded about
        cutoff_date = datetime.utcnow() - timedelta(days=days_threshold)
        
        old_prs = db.query(PullRequestNotification).filter(
            and_(
                PullRequestNotification.user_id == current_user.id,
                PullRequestNotification.pr_status == 'opened',
                PullRequestNotification.received_at <= cutoff_date,
                PullRequestNotification.slack_sent == False
            )
        ).order_by(PullRequestNotification.received_at.asc()).all()
        
        # Group by age for preview
        pr_groups = {
            "urgent": [],    # 8+ days
            "old": [],       # 3-7 days  
            "recent": []     # threshold to 3 days
        }
        
        now = datetime.utcnow()
        for pr in old_prs:
            days_old = (now - pr.received_at).days
            if days_old >= 8:
                pr_groups["urgent"].append(pr)
            elif days_old >= 3:
                pr_groups["old"].append(pr)
            else:
                pr_groups["recent"].append(pr)
        
        # Format response
        preview_data = []
        for group, prs in pr_groups.items():
            for pr in prs:
                days_old = (now - pr.received_at).days
                preview_data.append({
                    "id": str(pr.id),
                    "repo_name": pr.repo_name,
                    "pr_title": pr.pr_title,
                    "pr_link": pr.pr_link,
                    "days_old": days_old,
                    "urgency": group,
                    "received_at": pr.received_at.isoformat()
                })
        
        return {
            "total_prs": len(old_prs),
            "threshold_days": days_threshold,
            "would_remind_about": preview_data,
            "summary": {
                "urgent": len(pr_groups["urgent"]),
                "old": len(pr_groups["old"]),
                "recent": len(pr_groups["recent"])
            }
        }
    
    except Exception as e:
        logger.error(f"Error generating reminder preview for {current_user.email}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating preview: {str(e)}"
        )

@router.get("/reminder-stats", status_code=status.HTTP_200_OK)
async def get_reminder_statistics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get statistics about reminders for the current user
    """
    logger.info(f"Reminder statistics requested by {current_user.email}")
    
    try:
        # Get various counts
        total_prs = db.query(PullRequestNotification).filter(
            PullRequestNotification.user_id == current_user.id
        ).count()
        
        open_prs = db.query(PullRequestNotification).filter(
            and_(
                PullRequestNotification.user_id == current_user.id,
                PullRequestNotification.pr_status == 'opened'
            )
        ).count()
        
        slack_sent = db.query(PullRequestNotification).filter(
            and_(
                PullRequestNotification.user_id == current_user.id,
                PullRequestNotification.slack_sent == True
            )
        ).count()
        
        # Old PRs needing attention
        old_threshold = datetime.utcnow() - timedelta(days=3)
        old_open_prs = db.query(PullRequestNotification).filter(
            and_(
                PullRequestNotification.user_id == current_user.id,
                PullRequestNotification.pr_status == 'opened',
                PullRequestNotification.received_at <= old_threshold
            )
        ).count()
        
        # PRs that could be reminded about (old, open, not yet sent to Slack)
        remindable_prs = db.query(PullRequestNotification).filter(
            and_(
                PullRequestNotification.user_id == current_user.id,
                PullRequestNotification.pr_status == 'opened',
                PullRequestNotification.received_at <= old_threshold,
                PullRequestNotification.slack_sent == False
            )
        ).count()
        
        slack_connected = current_user.slack_connection is not None
        
        return {
            "total_prs": total_prs,
            "open_prs": open_prs,
            "old_open_prs": old_open_prs,
            "remindable_prs": remindable_prs,
            "slack_notifications_sent": slack_sent,
            "slack_connected": slack_connected,
            "slack_team": current_user.slack_connection.team_name if slack_connected else None,
            "reminder_eligible": slack_connected and remindable_prs > 0
        }
    
    except Exception as e:
        logger.error(f"Error getting reminder statistics for {current_user.email}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting statistics: {str(e)}"
        )