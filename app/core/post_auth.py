from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from app.core.config import settings
from app.core.logger import get_module_logger
from typing import Annotated
import secrets

logger = get_module_logger(__name__, 'logs/postmark_auth.log')
security = HTTPBasic()

POSTMARK_USERNAME = settings.WEBHOOK_USERNAME
POSTMARK_PASSWORD = settings.WEBHOOK_PASSWORD

def verify_postmark_credentials(credentials: Annotated[HTTPBasicCredentials, Depends(security)])-> bool:
    """
        verify Postmark webhook HTTP Basic Auth Credentials

        Args:
            credentials: HTTP Basic Auth credentials from request
        Returns:
             bool: True if credentials are valid
        
        Raises:
            HTTPException: 401 if credentials are valid
    """
    try:
        correct_username = secrets.compare_digest(
            credentials.username.encode("utf8"),
            POSTMARK_USERNAME.encode("utf8")
        )
        correct_password = secrets.compare_digest(
            credentials.password.encode("utf8"),
            POSTMARK_PASSWORD.encode("utf8")
        )
        if correct_username and correct_password:
            logger.info("Postmark webhook authentication successful")
            return True
        else:
            logger.warning("Failed Postmark authentication attempt from username:: {credentials.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Postmark webhook credential",
                headers={"www-Authenticate": "Basic"},
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during Postmark authentication: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication Failed",
            headers={"WWW-Authenicate": "Basic"},
        )
    
def get_auth_header()->str:
    """
        Generate the Authentication header value for testing
        Returns: "Basic <base64_encoded_credentials>"
    """
    import base64
    credentials = f"{POSTMARK_USERNAME}:{POSTMARK_PASSWORD}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"