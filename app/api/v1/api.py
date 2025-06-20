# =============================================================================
# app/api/v1/api.py (Updated with webhook)
# =============================================================================
from fastapi import APIRouter
from app.api.v1.endpoints import auth, users, slack_auth, postmark_webhook, pr_management, slack_reminders

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(slack_auth.router, prefix="/auth", tags=["Slack Authentication"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
# api_router.include_router(email.router, prefix="/email", tags=["Email Processing"])
api_router.include_router(postmark_webhook.router, prefix="/webhook", tags=["Postmark Webhook"])
api_router.include_router(pr_management.router, prefix="/pr", tags=["Pull Request Management"])
api_router.include_router(slack_reminders.router, prefix="/reminders", tags=["Slack Reminders"])

