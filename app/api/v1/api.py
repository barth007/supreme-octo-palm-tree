# =============================================================================
# app/api/v1/api.py
# =============================================================================
from fastapi import APIRouter
from app.api.v1.endpoints import auth, users, slack_auth

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(slack_auth.router, prefix="/auth", tags=["Slack Authentication"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])