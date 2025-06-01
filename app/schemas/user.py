# =============================================================================
# app/schemas/user.py
# =============================================================================
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr

class UserBase(BaseModel):
    name: str
    email: EmailStr

class UserCreate(UserBase):
    profile_image: Optional[str] = None

class UserUpdate(BaseModel):
    name: Optional[str] = None
    profile_image: Optional[str] = None

class UserResponse(UserBase):
    id: str
    profile_image: Optional[str]
    created_at: datetime
    updated_at: datetime

class GoogleUserInfo(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    picture: Optional[str] = None


    class Config:
        orm_mode = True
