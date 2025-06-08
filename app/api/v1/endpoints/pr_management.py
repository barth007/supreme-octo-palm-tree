# =============================================================================
# app/api/v1/endpoints/pr_management.py
# =============================================================================
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
    logger.info(f"Getting PR notifications for user: {current_user.email}")
    
    # Validate sort parameters
    valid_sort_fields = ["received_at", "pr_title", "repo_name", "created_at"]
    if sort_by not in valid_sort_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid sort field. Must be one of: {valid_sort_fields}"
        )
    
    if sort_order not in ["asc", "desc"]:
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
    
    # Get filtered notifications
    result = PRManagementService.get_user_pr_notifications(
        db, str(current_user.id), filters
    )
    
    logger.info(f"Retrieved {len(result.notifications)} PR notifications")
    return result

@router.get("/notifications/{notification_id}", response_model=PRNotificationResponse, status_code=status.HTTP_200_OK)
async def get_pr_notification_by_id(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get specific PR notification by ID
    """
    logger.info(f"Getting PR notification {notification_id} for user: {current_user.email}")
    
    notification = PRManagementService.get_pr_notification_by_id(
        db, notification_id, str(current_user.id)
    )
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PR notification not found"
        )
    
    return notification

@router.delete("/notifications/{notification_id}", status_code=status.HTTP_200_OK)
async def delete_pr_notification(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a specific PR notification
    """
    logger.info(f"Deleting PR notification {notification_id} for user: {current_user.email}")
    
    success = PRManagementService.delete_pr_notification(
        db, notification_id, str(current_user.id)
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PR notification not found"
        )
    
    return {"message": "PR notification deleted successfully"}

@router.get("/stats", response_model=PRStatsResponse, status_code=status.HTTP_200_OK)
async def get_pr_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get PR notification statistics for the current user
    """
    logger.info(f"Getting PR stats for user: {current_user.email}")
    
    stats = PRManagementService.get_user_pr_stats(db, str(current_user.id))
    return stats

@router.get("/summary", response_model=PRSummaryResponse, status_code=status.HTTP_200_OK)
async def get_pr_summary(
    days: int = Query(7, ge=1, le=365, description="Number of days to summarize"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get PR activity summary for the last X days
    """
    logger.info(f"Getting PR summary for user: {current_user.email} (last {days} days)")
    
    summary = PRManagementService.get_pr_summary(db, str(current_user.id), days)
    return summary

@router.get("/repositories", status_code=status.HTTP_200_OK)
async def get_user_repositories(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get list of repositories that have sent PR notifications to this user
    """
    logger.info(f"Getting repositories for user: {current_user.email}")
    
    repos = PRManagementService.get_user_repositories(db, str(current_user.id))
    return {"repositories": repos}

@router.post("/notifications/{notification_id}/mark-slack-sent", status_code=status.HTTP_200_OK)
async def mark_notification_slack_sent(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mark a notification as sent to Slack (manual override)
    """
    logger.info(f"Marking notification {notification_id} as Slack sent for user: {current_user.email}")
    
    success = PRManagementService.mark_slack_sent(db, notification_id, str(current_user.id))
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PR notification not found"
        )
    
    return {"message": "Notification marked as Slack sent"}

@router.get("/pending-slack", response_model=PRNotificationList, status_code=status.HTTP_200_OK)
async def get_pending_slack_notifications(
    limit: int = Query(50, ge=1, le=200, description="Maximum number of notifications"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get notifications that haven't been sent to Slack yet
    """
    logger.info(f"Getting pending Slack notifications for user: {current_user.email}")
    
    filters = PRFilterParams(
        slack_sent=False,
        limit=limit,
        sort_by="received_at",
        sort_order="asc"
    )
    
    result = PRManagementService.get_user_pr_notifications(
        db, str(current_user.id), filters
    )
    
    return result

@router.get("/old-prs", response_model=PRNotificationList, status_code=status.HTTP_200_OK)
async def get_old_pr_notifications(
    days_old: int = Query(7, ge=1, description="PRs older than X days"),
    status_filter: Optional[str] = Query("open", description="Filter by PR status"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of notifications"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get old PR notifications for reminders (useful for follow-ups)
    """
    logger.info(f"Getting old PR notifications for user: {current_user.email} (older than {days_old} days)")
    
    filters = PRFilterParams(
        status=status_filter,
        days_old=days_old,
        limit=limit,
        sort_by="received_at",
        sort_order="asc"
    )
    
    result = PRManagementService.get_user_pr_notifications(
        db, str(current_user.id), filters
    )
    
    return result

# Bulk Operations
@router.post("/notifications/bulk-delete", status_code=status.HTTP_200_OK)
async def bulk_delete_notifications(
    notification_ids: List[str],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete multiple notifications at once
    """
    logger.info(f"Bulk deleting {len(notification_ids)} notifications for user: {current_user.email}")
    
    result = PRManagementService.bulk_delete_notifications(
        db, notification_ids, str(current_user.id)
    )
    
    return result

@router.post("/notifications/bulk-mark-slack-sent", status_code=status.HTTP_200_OK)
async def bulk_mark_slack_sent(
    notification_ids: List[str],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mark multiple notifications as sent to Slack
    """
    logger.info(f"Bulk marking {len(notification_ids)} notifications as Slack sent for user: {current_user.email}")
    
    result = PRManagementService.bulk_mark_slack_sent(
        db, notification_ids, str(current_user.id)
    )
    
    return result

# Search and Analytics
@router.get("/search", status_code=status.HTTP_200_OK)
async def search_pr_notifications(
    q: str = Query(..., description="Search query"),
    fields: Optional[str] = Query("pr_title,repo_name,subject", description="Comma-separated fields to search"),
    date_from: Optional[datetime] = Query(None, description="Start date for search range"),
    date_to: Optional[datetime] = Query(None, description="End date for search range"),
    exact: bool = Query(False, description="Exact match instead of partial"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Advanced search for PR notifications
    """
    logger.info(f"Searching PR notifications for user: {current_user.email} with query: {q}")
    
    search_fields = fields.split(",") if fields else ["pr_title", "repo_name", "subject"]
    
    results = PRManagementService.search_pr_notifications(
        db, str(current_user.id), q, search_fields, date_from, date_to, exact
    )
    
    return {
        "query": q,
        "results": results,
        "total_matches": len(results)
    }

@router.get("/repositories/{repo_name}/stats", status_code=status.HTTP_200_OK)
async def get_repository_detailed_stats(
    repo_name: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed statistics for a specific repository
    """
    logger.info(f"Getting detailed stats for repository: {repo_name} for user: {current_user.email}")
    
    stats = PRManagementService.get_repository_stats(
        db, str(current_user.id), repo_name
    )
    
    if not stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found or no notifications"
        )
    
    return stats

# Utility endpoints
@router.get("/export", status_code=status.HTTP_200_OK)
async def export_pr_notifications(
    format: str = Query("json", description="Export format: json, csv"),
    days: Optional[int] = Query(None, description="Limit to last X days"),
    repo_filter: Optional[str] = Query(None, description="Filter by repository"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Export PR notifications in various formats
    """
    logger.info(f"Exporting PR notifications for user: {current_user.email} in {format} format")
    
    # Build filters for export
    filters = PRFilterParams(
        repo_name=repo_filter,
        days_old=days,
        limit=10000,  # Large limit for export
        sort_by="received_at",
        sort_order="desc"
    )
    
    result = PRManagementService.get_user_pr_notifications(
        db, str(current_user.id), filters
    )
    
    if format.lower() == "csv":
        # Convert to CSV format
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Headers
        writer.writerow([
            "ID", "Repository", "PR Title", "PR Number", "Status", 
            "Received At", "Slack Sent", "Is Forwarded", "PR Link"
        ])
        
        # Data rows
        for notification in result.notifications:
            writer.writerow([
                notification.id,
                notification.repo_name or "",
                notification.pr_title,
                notification.pr_number or "",
                notification.pr_status or "",
                notification.received_at.isoformat(),
                notification.slack_sent,
                notification.is_forwarded,
                notification.pr_link or ""
            ])
        
        csv_content = output.getvalue()
        output.close()
        
        from fastapi.responses import Response
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=pr_notifications.csv"}
        )
    
    # Default JSON format
    return {
        "format": format,
        "exported_at": datetime.utcnow().isoformat(),
        "total_records": result.total_count,
        "data": result.notifications
    }