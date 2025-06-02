# =============================================================================
# app/schemas/slack.py
# =============================================================================
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class SlackConnectionBase(BaseModel):
    slack_user_id: str
    slack_team_id: str
    team_name: Optional[str] = None

class SlackConnectionCreate(SlackConnectionBase):
    access_token: str

class SlackConnectionResponse(SlackConnectionBase):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class SlackMessageRequest(BaseModel):
    repo_name: str
    pr_title: str
    pr_url: str

class SlackTestMessageRequest(BaseModel):
    message: str = "Test notification from your FastAPI app! 🚀"