# =============================================================================
# app/services/user_service.py
# =============================================================================
import uuid
from typing import Optional
from sqlalchemy.orm import Session, joinedload
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.core.logger import get_module_logger
logger = get_module_logger(__name__, "logs/user_service.log")

class UserService:
    @staticmethod
    def get_user_by_email(db: Session, email: str) -> Optional[User]:
        """Get user by email"""
        logger.info(f"Querying database for user with email: {email}")
        return db.query(User).filter(User.email == email).first()
    

    @staticmethod
    def get_user_by_id(db: Session, user_id: str) -> Optional[User]:
        """Get user by ID with Slack connection"""
        logger.info(f"Querying database for user with ID: {user_id}")
        # Convert string to UUID if needed
        if isinstance(user_id, str):
            user_id = uuid.UUID(user_id)
        return db.query(User).options(joinedload(User.slack_connection)).filter(User.id == user_id).first()
    
    @staticmethod
    def create_user(db: Session, user_data: UserCreate) -> User:
        """Create new user"""
        user = User(**user_data.model_dump())
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(f"User created with email: {user.email}")
        return user
    
    @staticmethod
    def update_user(db: Session, user: User, user_data: UserUpdate) -> User:
        """Update existing user"""
        update_data = user_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)
        db.commit()
        db.refresh(user)
        logger.info(f"User updated with email: {user.email}")
        return user