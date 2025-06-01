# =============================================================================
# app/schemas/token.py
# =============================================================================
from pydantic import BaseModel
from app.schemas.user import UserResponse

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

class TokenData(BaseModel):
    email: str