# =============================================================================
# app/utils/oauth.py
# =============================================================================
from authlib.integrations.starlette_client import OAuth
from app.core.config import settings
from app.core.logger import get_module_logger

oauth = OAuth()

# ⭐ ADD LOGGING TO OAUTH REGISTRATION
import logging
logger = get_module_logger(__name__, 'logs/oauth.log')

oauth.register(
    name='google',
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

# ⭐ ENHANCED SLACK OAUTH REGISTRATION WITH DEBUGGING
if settings.SLACK_CLIENT_ID and settings.SLACK_CLIENT_SECRET:
    logger.info(f"Registering Slack OAuth with client_id: {settings.SLACK_CLIENT_ID[:10]}...")
    logger.info(f"Slack redirect URI: {settings.SLACK_REDIRECT_URI}")
    
    oauth.register(
        name='slack',
        client_id=settings.SLACK_CLIENT_ID,
        client_secret=settings.SLACK_CLIENT_SECRET,
        authorize_url='https://slack.com/oauth/v2/authorize',
        access_token_url='https://slack.com/api/oauth.v2.access',
        api_base_url='https://slack.com/api/',
        client_kwargs={
            'scope': 'chat:write users:read'
        }
    )
    logger.info("✅ Slack OAuth registered successfully")
else:
    logger.warning("❌ Slack OAuth not registered - missing credentials")
    logger.warning(f"SLACK_CLIENT_ID: {'SET' if settings.SLACK_CLIENT_ID else 'NOT SET'}")
    logger.warning(f"SLACK_CLIENT_SECRET: {'SET' if settings.SLACK_CLIENT_SECRET else 'NOT SET'}")