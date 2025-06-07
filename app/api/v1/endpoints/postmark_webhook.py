# =============================================================================
# app/api/v1/endpoints/postmark_webhook.py
# =============================================================================
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.email import PostmarkInboundWebhook, WebhookProcessResponse
from app.services.pr_perser_service import PRParserService
from app.services.pr_notification_service import PRNotificationService
from app.core.post_auth import verify_postmark_credentials
from app.core.logger import get_module_logger

logger = get_module_logger(__name__, "logs/postmark_webhook.log")

router = APIRouter()

@router.post("/inbound", response_model=WebhookProcessResponse, status_code=status.HTTP_200_OK)
async def process_postmark_webhook(
    webhook_data: PostmarkInboundWebhook,
    db: Session = Depends(get_db),
    authenticated: bool = Depends(verify_postmark_credentials)
):
    """
    Process inbound email webhook from Postmark
    Requires HTTP Basic Auth: username="postmark", password="supersecure"
    Extracts PR information and stores it in the database
    """
    try:
        logger.info(f"Processing Postmark webhook - MessageID: {webhook_data.MessageID}")
        logger.info(f"Subject: {webhook_data.Subject}")
        logger.info(f"From: {webhook_data.From} -> To: {webhook_data.OriginalRecipient}")
        
        # Extract recipient email to identify the user
        recipient_email = PRParserService.extract_recipient_email(webhook_data)
        logger.debug(f"Processing email for recipient: {recipient_email}")
        
        # Find user by recipient email
        user = PRNotificationService.find_user_by_email(db, recipient_email)
        if not user:
            logger.error(f"No user found for email: {recipient_email}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User not found for email address: {recipient_email}"
            )
        
        logger.info(f"Found user: {user.email} (ID: {user.id})")
        
        # Extract PR data from email content
        extracted_data = PRParserService.extract_pr_data(webhook_data)
        logger.info(f"Extracted PR data: {extracted_data.model_dump()}")
        
        # Create PR notification record
        notification = PRNotificationService.create_pr_notification(
            db, webhook_data, extracted_data, user
        )
        
        # Create Slack payload (but don't send yet)
        slack_payload = PRParserService.create_slack_payload(
            extracted_data, webhook_data, user.name
        )
        
        logger.info(f"Successfully processed webhook and created notification: {notification.id}")
        
        return WebhookProcessResponse(
            success=True,
            message="Webhook processed and PR notification saved successfully",
            notification_id=str(notification.id),
            extracted_data=extracted_data,
            slack_payload=slack_payload
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Error processing Postmark webhook: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing webhook: {str(e)}"
        )

@router.get("/health", status_code=status.HTTP_200_OK)
async def webhook_health_check():
    """Health check endpoint for webhook service"""
    return {"status": "healthy", "service": "postmark_webhook"}

@router.post("/test", response_model=WebhookProcessResponse, status_code=status.HTTP_200_OK)
async def test_webhook_processing(
    test_payload: dict,
    db: Session = Depends(get_db),
    authenticated: bool = Depends(verify_postmark_credentials)
):
    """
    Test endpoint for webhook processing
    Accepts simplified test data and converts to Postmark format
    """
    try:
        # Create mock Postmark payload from test data
        mock_webhook = PostmarkInboundWebhook(
            FromName=test_payload.get("from_name", "Test User"),
            MessageStream="inbound",
            From=test_payload.get("from_email", "test@github.com"),
            FromFull={
                "Email": test_payload.get("from_email", "test@github.com"),
                "Name": test_payload.get("from_name", "Test User")
            },
            To=test_payload.get("to_email", "user@example.com"),
            ToFull=[{
                "Email": test_payload.get("to_email", "user@example.com"),
                "Name": "Test Recipient"
            }],
            OriginalRecipient=test_payload.get("to_email", "user@example.com"),
            Subject=test_payload.get("subject", "Fwd: [test/repo] Test PR (#123)"),
            MessageID=test_payload.get("message_id", f"test-{int(datetime.now().timestamp())}"),
            Date=test_payload.get("date", datetime.now().strftime("%a, %d %b %Y %H:%M:%S %z")),
            TextBody=test_payload.get("text_body", "Test PR notification"),
            HtmlBody=test_payload.get("html_body"),
            Headers=test_payload.get("headers", [])
        )
        
        # Process using the same logic as main endpoint
        return await process_postmark_webhook(mock_webhook, db, authenticated)
        
    except Exception as e:
        logger.error(f"Error in test webhook processing: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Test processing failed: {str(e)}"
        )