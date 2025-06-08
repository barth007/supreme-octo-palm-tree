# =============================================================================
# app/schemas/reminders.py
# =============================================================================
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class ReminderSettings(BaseModel):
    """User reminder preferences"""
    enabled: bool = True
    reminder_threshold_days: int = Field(2, ge=1, le=30, description="Send reminders for PRs older than X days")
    max_reminders_per_session: int = Field(10, ge=1, le=50, description="Maximum reminders per session")
    daily_summary_enabled: bool = True
    reminder_time_hour: int = Field(9, ge=0, le=23, description="Preferred hour for reminders (24h format)")

class PRReminderItem(BaseModel):
    """Individual PR item for reminders"""
    id: str
    repo_name: Optional[str] = None
    pr_title: str
    pr_link: Optional[str] = None
    pr_number: Optional[str] = None
    days_old: int
    urgency: str = Field(..., description="recent, old, or urgent")
    received_at: datetime

class ReminderPreviewResponse(BaseModel):
    """Preview of what would be reminded about"""
    total_prs: int
    threshold_days: int
    would_remind_about: List[PRReminderItem]
    summary: Dict[str, int]  # urgent, old, recent counts

class ReminderStatsResponse(BaseModel):
    """Statistics about user's reminders"""
    total_prs: int
    open_prs: int
    old_open_prs: int
    remindable_prs: int
    slack_notifications_sent: int
    slack_connected: bool
    slack_team: Optional[str] = None
    reminder_eligible: bool

class ManualReminderRequest(BaseModel):
    """Request for manual reminder triggering"""
    days_threshold: int = Field(2, ge=1, le=30)
    max_reminders: int = Field(10, ge=1, le=50)
    send_as_bulk: bool = True  # Send as single message vs individual messages

class ReminderResponse(BaseModel):
    """Response after sending reminders"""
    message: str
    sent_count: int
    prs_reminded: Optional[List[PRReminderItem]] = None
    slack_message_id: Optional[str] = None

class DailySummaryData(BaseModel):
    """Data for daily summary"""
    total_open: int
    new_today: int
    needs_attention: int
    most_active_repo: Optional[str] = None
    action_items: List[str] = []

class BackgroundTaskResponse(BaseModel):
    """Response for background task triggers"""
    message: str
    status: str = "processing"
    task_id: Optional[str] = None
    parameters: Dict[str, Any] = {}

class ReminderScheduleRequest(BaseModel):
    """Request for scheduling reminders"""
    schedule_type: str = Field(..., description="daily, weekly, or custom")
    time_of_day: int = Field(9, ge=0, le=23, description="Hour of day (24h format)")
    days_of_week: Optional[List[int]] = Field(None, description="Days of week (0=Monday)")
    threshold_days: int = Field(2, ge=1, le=30)

class SlackTestResponse(BaseModel):
    """Response for Slack connection test"""
    message: str
    connection_working: bool
    slack_team: Optional[str] = None
    error: Optional[str] = None

class BulkReminderStats(BaseModel):
    """Statistics from bulk reminder operations"""
    total_users_processed: int
    successful_reminders: int
    failed_reminders: int
    total_prs_reminded: int
    processing_time_seconds: float
    errors: List[str] = []

class ReminderHistory(BaseModel):
    """History of sent reminders"""
    date: datetime
    reminder_type: str  # individual, bulk, daily_summary
    prs_count: int
    success: bool
    slack_message_id: Optional[str] = None

class ReminderMetrics(BaseModel):
    """Metrics about reminder system performance"""
    reminders_sent_today: int
    reminders_sent_this_week: int
    average_prs_per_reminder: float
    most_reminded_repo: Optional[str] = None
    response_rate: float  # How often reminders lead to action
    user_engagement_score: float