# =============================================================================
# app/utils/oauth.py
# =============================================================================
from authlib.integrations.starlette_client import OAuth
from app.core.config import settings

oauth = OAuth()

oauth.register(
    name='google',
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)
# Slack OAuth2
if settings.SLACK_CLIENT_ID and settings.SLACK_CLIENT_SECRET:
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