# =============================================================================
# app/api/v1/endpoints/postmark_webhook.py (COMPLETE UPDATED VERSION)
# =============================================================================
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from datetime import datetime
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
    # authenticated: bool = Depends(verify_postmark_credentials)  # Disabled for now
):
    """
    Process inbound email webhook from Postmark
    Handles both direct emails and forwarded emails with enhanced recipient extraction
    """
    try:
        logger.info(f"🔄 Processing Postmark webhook - MessageID: {webhook_data.MessageID}")
        logger.info(f"📧 Subject: {webhook_data.Subject}")
        logger.info(f"📨 From: {webhook_data.From} -> Webhook To: {webhook_data.OriginalRecipient}")
        
        # ⭐ ENHANCED: Extract the actual user email (handles forwarded emails)
        recipient_email = PRParserService.extract_recipient_email(webhook_data)
        logger.info(f"🎯 Extracted recipient email: {recipient_email}")
        
        # ⭐ HANDLE POSTMARK TEST EMAILS
        if ("postmarkapp.com" in recipient_email or 
            "inbound.postmarkapp.com" in recipient_email or
            "@inbound.postmarkapp.com" in recipient_email):
            
            logger.info(f"🧪 POSTMARK TEST EMAIL detected: {recipient_email}")
            logger.info("✅ Returning success response for Postmark test")
            
            # Create a successful test response
            from app.schemas.email import PRExtractionResult, SlackPayload
            
            test_extracted_data = PRExtractionResult(
                repo_name="test/repository",
                pr_title="Test PR from Postmark",
                pr_link="https://github.com/test/repository/pull/1",
                pr_number="1",
                pr_status="opened",
                is_forwarded=True,
                original_sender="notifications@github.com"
            )
            
            test_slack_payload = SlackPayload(
                text="🧪 Test webhook from Postmark",
                attachments=None,
                blocks=None
            )
            
            return WebhookProcessResponse(
                success=True,
                message="Postmark test email processed successfully",
                notification_id="postmark-test-notification",
                extracted_data=test_extracted_data,
                slack_payload=test_slack_payload
            )
        
        # ⭐ HANDLE REAL USER EMAILS
        # Find user by the extracted recipient email
        user = PRNotificationService.find_user_by_email(db, recipient_email)
        if not user:
            logger.error(f"❌ No user found for email: {recipient_email}")
            
            # Get list of available users for debugging
            try:
                from app.models.user import User
                available_users = db.query(User.email).limit(10).all()
                available_emails = [u.email for u in available_users]
                logger.info(f"💡 Available users in database: {available_emails}")
                
                error_detail = f"User not found for email: {recipient_email}. Available users: {available_emails}"
            except Exception as e:
                logger.error(f"Error getting available users: {e}")
                error_detail = f"User not found for email: {recipient_email}"
            
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_detail
            )
        
        logger.info(f"👤 Found user: {user.email} (ID: {user.id})")
        
        # ⭐ ENHANCED: Extract PR data from email content
        extracted_data = PRParserService.extract_pr_data(webhook_data)
        logger.info(f"📊 Extracted PR data:")
        logger.info(f"   📁 Repository: {extracted_data.repo_name}")
        logger.info(f"   📝 Title: {extracted_data.pr_title}")
        logger.info(f"   🔗 Link: {extracted_data.pr_link}")
        logger.info(f"   #️⃣ PR Number: {extracted_data.pr_number}")
        logger.info(f"   📊 Status: {extracted_data.pr_status}")
        logger.info(f"   📤 Is Forwarded: {extracted_data.is_forwarded}")
        
        # Create PR notification record
        notification = PRNotificationService.create_pr_notification(
            db, webhook_data, extracted_data, user
        )
        
        # Create Slack payload (but don't send yet)
        slack_payload = PRParserService.create_slack_payload(
            extracted_data, webhook_data, user.name
        )
        
        logger.info(f"✅ Successfully processed webhook and created notification: {notification.id}")
        logger.info(f"💾 Notification saved for user: {user.email}")
        
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
        logger.error(f"💥 Error processing Postmark webhook: {str(e)}", exc_info=True)
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
        return await process_postmark_webhook(mock_webhook, db)
        
    except Exception as e:
        logger.error(f"💥 Error in test webhook processing: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Test processing failed: {str(e)}"
        )

# ⭐ NEW: Debug endpoint to test email extraction
@router.post("/debug-extraction", status_code=status.HTTP_200_OK)
async def debug_email_extraction(webhook_data: PostmarkInboundWebhook):
    """
    Debug endpoint to test email extraction without saving to database
    Useful for testing different email formats
    """
    try:
        logger.info(f"🔍 DEBUG: Testing email extraction")
        
        # Extract recipient email
        recipient_email = PRParserService.extract_recipient_email(webhook_data)
        
        # Extract PR data
        extracted_data = PRParserService.extract_pr_data(webhook_data)
        
        # Check if forwarded
        is_forwarded = PRParserService._is_forwarded_email(webhook_data)
        
        debug_info = {
            "webhook_to": webhook_data.OriginalRecipient,
            "webhook_from": webhook_data.From,
            "extracted_recipient": recipient_email,
            "is_forwarded": is_forwarded,
            "extracted_pr_data": extracted_data.model_dump(),
            "text_body_preview": webhook_data.TextBody[:500] if webhook_data.TextBody else None
        }
        
        logger.info(f"🔍 Debug extraction results: {debug_info}")
        
        return {
            "success": True,
            "message": "Email extraction debug completed",
            "debug_info": debug_info
        }
        
    except Exception as e:
        logger.error(f"💥 Error in debug extraction: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "debug_info": None
        }

# ⭐ NEW: Test forwarded email endpoint
@router.post("/test-forwarded", response_model=WebhookProcessResponse, status_code=status.HTTP_200_OK)
async def test_forwarded_email():
    """
    Test endpoint with your exact forwarded email format
    """
    try:
        # Create test payload matching your forwarded email format
        test_webhook = PostmarkInboundWebhook(
            FromName="BARTHOLOMEW BASSEY",
            MessageStream="inbound",
            From="bartholomew.bassey@st.futminna.edu.ng",
            FromFull={
                "Email": "bartholomew.bassey@st.futminna.edu.ng",
                "Name": "BARTHOLOMEW BASSEY"
            },
            To="pr-notifications@yourapp.com",
            ToFull=[{
                "Email": "pr-notifications@yourapp.com",
                "Name": "PR Notifications"
            }],
            OriginalRecipient="pr-notifications@yourapp.com",
            Subject="Fwd: [barth007/dial-a-doc] Mydocapp (PR #37)",
            MessageID=f"test-forwarded-{int(datetime.now().timestamp())}",
            Date=datetime.now().strftime("%a, %d %b %Y %H:%M:%S %z"),
            TextBody="""---------- Forwarded message ---------
From: **BARTHOLOMEW BASSEY** <bartholomew.bassey@st.futminna.edu.ng>
Date: Sun, 8 Jun 2025 at 14:38
Subject: Fwd: [barth007/dial-a-doc] Mydocapp (PR #37)
To: <basseybartholomew237@gmail.com>

A new pull request has been created.

Repository: barth007/dial-a-doc
Title: Mydocapp
PR Link: https://github.com/barth007/dial-a-doc/pull/37

Please review this pull request.""",
            Headers=[]
        )
        
        # Test just the extraction
        recipient_email = PRParserService.extract_recipient_email(test_webhook)
        extracted_data = PRParserService.extract_pr_data(test_webhook)
        
        logger.info(f"🧪 Test forwarded email extraction:")
        logger.info(f"   📧 Extracted recipient: {recipient_email}")
        logger.info(f"   📁 Repository: {extracted_data.repo_name}")
        logger.info(f"   📝 Title: {extracted_data.pr_title}")
        logger.info(f"   📤 Is forwarded: {extracted_data.is_forwarded}")
        
        return WebhookProcessResponse(
            success=True,
            message=f"Test extraction completed. Recipient: {recipient_email}",
            notification_id="test-forwarded-extraction",
            extracted_data=extracted_data,
            slack_payload=PRParserService.create_slack_payload(extracted_data, test_webhook, "Test User")
        )
        
    except Exception as e:
        logger.error(f"💥 Error in test forwarded email: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Test forwarded email failed: {str(e)}"
        )