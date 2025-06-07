# =============================================================================
# app/schemas/email.py
# =============================================================================
from datetime import datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, EmailStr

# Postmark webhook schemas
class PostmarkEmailAddress(BaseModel):
    Email: EmailStr
    Name: Optional[str] = None
    MailboxHash: Optional[str] = None

class PostmarkAttachment(BaseModel):
    Name: str
    Content: str
    ContentType: str
    ContentLength: int

class PostmarkHeader(BaseModel):
    Name: str
    Value: str

class PostmarkInboundWebhook(BaseModel):
    FromName: Optional[str] = None
    MessageStream: Optional[str] = None
    From: EmailStr
    FromFull: PostmarkEmailAddress
    To: str
    ToFull: List[PostmarkEmailAddress]
    Cc: Optional[str] = None
    CcFull: Optional[List[PostmarkEmailAddress]] = []
    Bcc: Optional[str] = None
    BccFull: Optional[List[PostmarkEmailAddress]] = []
    OriginalRecipient: str
    Subject: str
    MessageID: str
    ReplyTo: Optional[str] = None
    MailboxHash: Optional[str] = None
    Date: str
    TextBody: Optional[str] = None
    HtmlBody: Optional[str] = None
    StrippedTextReply: Optional[str] = None
    RawEmail: Optional[str] = None
    Tag: Optional[str] = None
    Headers: Optional[List[PostmarkHeader]] = []
    Attachments: Optional[List[PostmarkAttachment]] = []


# PR schemas
class PRExtractionResult(BaseModel):
    repo_name: Optional[str] = None
    pr_title: str
    pr_link: Optional[str] = None
    pr_number: Optional[str] = None
    pr_status: Optional[str] = None
    is_forwarded: bool = False
    original_sender: Optional[str] = None


class SlackPayload(BaseModel):
    text: str
    attachments: Optional[List[Dict[str, Any]]] = None
    blocks: Optional[List[Dict[str, Any]]] = None

class WebhookProcessResponse(BaseModel):
    success: bool
    message: str
    notification_id: Optional[str] = None
    extracted_data: Optional[PRExtractionResult] = None
    slack_payload: Optional[SlackPayload] = None
    
    class Config:
        from_attributes = True

# Email processing response
class EmailProcessResponse(BaseModel):
    success: bool
    message: str
    pr_id: Optional[str] = None
    extracted_data: Optional[Dict[str, Any]] = None