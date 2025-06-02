# =============================================================================
# app/models/slack_connection.py
# =============================================================================
from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import BaseModel

class SlackConnection(BaseModel):
    __tablename__ = "slack_connections"
    
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True)
    slack_user_id = Column(String, nullable=False)
    slack_team_id = Column(String, nullable=False)
    access_token = Column(String, nullable=False)
    team_name = Column(String, nullable=True)
    
    # Relationship
    user = relationship("User", back_populates="slack_connection")