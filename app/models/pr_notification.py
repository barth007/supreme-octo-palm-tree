# =============================================================================
# app/models/pr_notification.py
# =============================================================================
from sqlalchemy import Column, String, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
from app.db.base import BaseModel

class PullRequestNotification(BaseModel):
    __tablename__ = "pull_request_notifications"
    
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    sender_email = Column(String, nullable=False, index=True)
    recipient_email = Column(String, nullable=False, index=True)
    repo_name = Column(String, nullable=True, index=True)
    pr_title = Column(String, nullable=False)
    pr_link = Column(String, nullable=True)
    subject = Column(String, nullable=False)
    received_at = Column(DateTime, nullable=False)
    message_id = Column(String, nullable=False, unique=True)
    raw_text = Column(Text, nullable=True)
    raw_html = Column(Text, nullable=True)
    slack_sent = Column(Boolean, default=False, nullable=False)
    
    # Additional fields for better tracking
    pr_number = Column(String, nullable=True)
    pr_status = Column(String, nullable=True)  # opened, merged, closed
    is_forwarded = Column(Boolean, default=False, nullable=False)  # Gmail forwarded email
    
    # Relationship
    user = relationship("User", back_populates="pr_notifications")
    
    def __repr__(self):
        return f"<PRNotification {self.repo_name} - {self.pr_title[:50]}...>"