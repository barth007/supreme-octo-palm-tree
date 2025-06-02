# =============================================================================
# app/models/user.py
# =============================================================================
from sqlalchemy import Column, String
from sqlalchemy.orm import relationship
from app.db.base import BaseModel

class User(BaseModel):
    __tablename__ = "users"
    
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    profile_image = Column(String, nullable=True)
    slack_connection = relationship("SlackConnection", back_populates="user", uselist=False)

