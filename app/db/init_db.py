# =============================================================================
# app/db/init_db.py
# =============================================================================
from app.db.base import Base
from app.db.session import engine
from app.models.user import User
from app.models.slack_connection import SlackConnection

def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)
