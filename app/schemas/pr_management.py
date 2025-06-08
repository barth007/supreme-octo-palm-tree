# =============================================================================
# app/schemas/pr_management.py
# =============================================================================
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class PRNotificationBase(BaseModel):
    sender_email: str
    recipient_email: str
    repo_name: Optional[str] = None
    pr_title: str
    pr_link: Optional[str] = None
    subject: str
    received_at: datetime
    message_id: str
    slack_sent: bool = False
    pr_number: Optional[str] = None
    pr_status: Optional[str] = None
    is_forwarded: bool = False

class PRNotificationResponse(PRNotificationBase):
    id: str
    user_id: str
    raw_text: Optional[str] = None
    raw_html: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class PRNotificationSummary(BaseModel):
    """Lightweight version without raw email content"""
    id: str
    repo_name: Optional[str] = None
    pr_title: str
    pr_link: Optional[str] = None
    pr_number: Optional[str] = None
    pr_status: Optional[str] = None
    received_at: datetime
    slack_sent: bool = False
    is_forwarded: bool = False
    
    class Config:
        from_attributes = True

class PRFilterParams(BaseModel):
    """Parameters for filtering PR notifications"""
    status: Optional[str] = None
    repo_name: Optional[str] = None
    days_old: Optional[int] = None
    slack_sent: Optional[bool] = None
    is_forwarded: Optional[bool] = None
    page: int = 1
    limit: int = 50
    sort_by: str = "received_at"
    sort_order: str = "desc"

class PRNotificationList(BaseModel):
    """Paginated list of PR notifications"""
    notifications: List[PRNotificationSummary]
    total_count: int
    page: int
    limit: int
    total_pages: int
    has_next: bool
    has_previous: bool

class PRStatsResponse(BaseModel):
    """Statistics about user's PR notifications"""
    total_notifications: int
    slack_sent: int
    pending_slack: int
    by_status: Dict[str, int]
    by_repository: Dict[str, int]
    forwarded_emails: int
    recent_activity: Dict[str, int]  # Last 7 days
    
    # Additional useful stats
    oldest_pending_pr: Optional[datetime] = None
    newest_pr: Optional[datetime] = None
    most_active_repo: Optional[str] = None

class PRSummaryResponse(BaseModel):
    """Summary of PR activity for a time period"""
    period_days: int
    total_notifications: int
    new_prs: int
    merged_prs: int
    closed_prs: int
    repositories_involved: List[str]
    daily_activity: Dict[str, int]  # Date -> count
    
    # Actionable insights
    pending_reviews: int
    old_open_prs: int  # PRs older than threshold
    notification_rate: float  # PRs per day

class RepositoryStats(BaseModel):
    """Statistics for a specific repository"""
    repo_name: str
    total_prs: int
    open_prs: int
    merged_prs: int
    closed_prs: int
    last_activity: Optional[datetime] = None
    avg_response_time: Optional[float] = None  # In hours

class PRActivityTimeline(BaseModel):
    """Timeline of PR activity"""
    date: str
    notifications: List[PRNotificationSummary]
    count: int

class PRBulkOperation(BaseModel):
    """For bulk operations on PR notifications"""
    notification_ids: List[str]
    operation: str  # "delete", "mark_slack_sent", etc.

class PRBulkOperationResponse(BaseModel):
    """Response for bulk operations"""
    success: bool
    processed_count: int
    failed_count: int
    errors: List[str] = []

class PRReminderSettings(BaseModel):
    """User settings for PR reminders"""
    enabled: bool = True
    days_threshold: int = 7  # Send reminder for PRs older than X days
    reminder_frequency: str = "daily"  # daily, weekly
    slack_reminders: bool = True
    email_reminders: bool = False

class PRSearchRequest(BaseModel):
    """Advanced search parameters"""
    query: str
    search_fields: List[str] = ["pr_title", "repo_name", "subject"]
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    exact_match: bool = False

class PRSearchResponse(BaseModel):
    """Search results"""
    results: List[PRNotificationSummary]
    total_matches: int
    search_query: str
    execution_time_ms: float