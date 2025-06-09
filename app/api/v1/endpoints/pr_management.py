# app/api/v1/endpoints/pr_management.py (FIXED with better error handling)
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime, timedelta
from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services.pr_management_service import PRManagementService
from app.schemas.pr_management import (
    PRNotificationResponse, 
    PRNotificationList, 
    PRFilterParams,
    PRStatsResponse,
    PRSummaryResponse
)
from app.core.logger import get_module_logger

logger = get_module_logger(__name__, "logs/pr_management.log")

router = APIRouter()

@router.get("/notifications", response_model=PRNotificationList, status_code=status.HTTP_200_OK)
async def get_pr_notifications(
    # Filtering parameters
    status_filter: Optional[str] = Query(None, description="Filter by PR status: open, merged, closed"),
    repo_filter: Optional[str] = Query(None, description="Filter by repository name"),
    days_old: Optional[int] = Query(None, description="Filter PRs older than X days"),
    slack_sent: Optional[bool] = Query(None, description="Filter by Slack notification status"),
    is_forwarded: Optional[bool] = Query(None, description="Filter forwarded emails"),
    
    # Pagination parameters
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=200, description="Items per page"),
    
    # Sorting
    sort_by: str = Query("received_at", description="Sort by: received_at, pr_title, repo_name"),
    sort_order: str = Query("desc", description="Sort order: asc, desc"),
    
    # Dependencies
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get paginated list of PR notifications with filtering options
    """
    try:
        logger.info(f"Getting PR notifications for user: {current_user.email} (ID: {current_user.id})")
        logger.info(f"Filters: status={status_filter}, repo={repo_filter}, days_old={days_old}, slack_sent={slack_sent}, page={page}")
        
        # Validate sort parameters
        valid_sort_fields = ["received_at", "pr_title", "repo_name", "created_at"]
        if sort_by not in valid_sort_fields:
            logger.error(f"Invalid sort field: {sort_by}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid sort field. Must be one of: {valid_sort_fields}"
            )
        
        if sort_order not in ["asc", "desc"]:
            logger.error(f"Invalid sort order: {sort_order}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sort order must be 'asc' or 'desc'"
            )
        
        # Create filter parameters
        filters = PRFilterParams(
            status=status_filter,
            repo_name=repo_filter,
            days_old=days_old,
            slack_sent=slack_sent,
            is_forwarded=is_forwarded,
            page=page,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        logger.info(f"Created filter params: {filters}")
        
        # Get filtered notifications - make sure to pass user ID as string
        user_id_str = str(current_user.id)
        logger.info(f"Using user_id: {user_id_str} (type: {type(user_id_str)})")
        
        result = PRManagementService.get_user_pr_notifications(
            db, user_id_str, filters
        )
        
        logger.info(f"Retrieved {len(result.notifications)} PR notifications (total: {result.total_count})")
        return result
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_pr_notifications: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

@router.get("/notifications/{notification_id}", response_model=PRNotificationResponse, status_code=status.HTTP_200_OK)
async def get_pr_notification_by_id(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get specific PR notification by ID
    """
    try:
        logger.info(f"Getting PR notification {notification_id} for user: {current_user.email}")
        
        notification = PRManagementService.get_pr_notification_by_id(
            db, notification_id, str(current_user.id)
        )
        
        if not notification:
            logger.warning(f"PR notification {notification_id} not found for user {current_user.id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="PR notification not found"
            )
        
        return notification
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting PR notification {notification_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

@router.delete("/notifications/{notification_id}", status_code=status.HTTP_200_OK)
async def delete_pr_notification(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a specific PR notification
    """
    try:
        logger.info(f"Deleting PR notification {notification_id} for user: {current_user.email}")
        
        success = PRManagementService.delete_pr_notification(
            db, notification_id, str(current_user.id)
        )
        
        if not success:
            logger.warning(f"Failed to delete PR notification {notification_id} for user {current_user.id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="PR notification not found"
            )
        
        logger.info(f"Successfully deleted PR notification {notification_id}")
        return {"message": "PR notification deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting PR notification {notification_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

@router.get("/stats", response_model=PRStatsResponse, status_code=status.HTTP_200_OK)
async def get_pr_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get PR notification statistics for the current user
    """
    try:
        logger.info(f"Getting PR stats for user: {current_user.email}")
        
        stats = PRManagementService.get_user_pr_stats(db, str(current_user.id))
        
        logger.info(f"Retrieved PR stats: total={stats.total_notifications}, slack_sent={stats.slack_sent}")
        return stats
        
    except Exception as e:
        logger.error(f"Error getting PR stats: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

@router.post("/notifications/{notification_id}/mark-slack-sent", status_code=status.HTTP_200_OK)
async def mark_notification_slack_sent(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mark a notification as sent to Slack (manual override)
    """
    try:
        logger.info(f"Marking notification {notification_id} as Slack sent for user: {current_user.email}")
        
        success = PRManagementService.mark_slack_sent(db, notification_id, str(current_user.id))
        
        if not success:
            logger.warning(f"Failed to mark notification {notification_id} as Slack sent")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="PR notification not found"
            )
        
        logger.info(f"Successfully marked notification {notification_id} as Slack sent")
        return {"message": "Notification marked as Slack sent"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking notification as Slack sent: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

@router.get("/repositories", status_code=status.HTTP_200_OK)
async def get_user_repositories(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get list of repositories that have sent PR notifications to this user
    """
    try:
        logger.info(f"Getting repositories for user: {current_user.email}")
        
        repos = PRManagementService.get_user_repositories(db, str(current_user.id))
        
        logger.info(f"Found {len(repos)} repositories for user")
        return {"repositories": repos}
        
    except Exception as e:
        logger.error(f"Error getting user repositories: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )