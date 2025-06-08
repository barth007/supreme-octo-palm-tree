# =============================================================================
# app/services/pr_perser_service.py (COMPLETE UPDATED VERSION)
# =============================================================================
import re
from typing import Optional, List, Dict, Any
from datetime import datetime
from bs4 import BeautifulSoup
from app.schemas.email import PostmarkInboundWebhook, PRExtractionResult, SlackPayload
from app.core.logger import get_module_logger

logger = get_module_logger(__name__, "logs/pr_parser.log")

class PRParserService:
    """Enhanced service for parsing GitHub PR notifications from Postmark webhooks"""
    
    @staticmethod
    def extract_recipient_email(webhook_data: PostmarkInboundWebhook) -> str:
        """
        Extract the actual user email from webhook data
        Handles both direct emails and forwarded emails
        """
        logger.info(f"🔍 Extracting recipient email from webhook")
        logger.info(f"📧 Webhook To: {webhook_data.OriginalRecipient}")
        logger.info(f"📧 Webhook From: {webhook_data.From}")
        logger.info(f"📧 Subject: {webhook_data.Subject}")
        
        # Check if this is a forwarded email
        is_forwarded = PRParserService._is_forwarded_email(webhook_data)
        logger.info(f"📤 Is forwarded email: {is_forwarded}")
        
        if is_forwarded:
            # ⭐ FOR FORWARDED EMAILS: Extract original recipient from email content
            original_recipient = PRParserService._extract_original_recipient_from_content(webhook_data)
            if original_recipient:
                logger.info(f"✅ Found original recipient in forwarded content: {original_recipient}")
                return original_recipient
            else:
                logger.warning(f"⚠️  Could not extract original recipient from forwarded content")
                # Fallback to webhook recipient
                return webhook_data.OriginalRecipient
        else:
            # ⭐ FOR DIRECT EMAILS: Use the webhook recipient
            logger.info(f"📨 Direct email, using webhook recipient: {webhook_data.OriginalRecipient}")
            return webhook_data.OriginalRecipient
    
    @staticmethod
    def _extract_original_recipient_from_content(webhook_data: PostmarkInboundWebhook) -> Optional[str]:
        """
        Extract the original 'To:' email from forwarded message content
        Looks for patterns like: "To: <email@domain.com>" or "To: email@domain.com"
        """
        content = webhook_data.TextBody or ""
        
        logger.debug(f"🔍 Searching for original recipient in content...")
        logger.debug(f"📄 Content preview: {content[:300]}...")
        
        # Common patterns for forwarded email "To:" lines
        patterns = [
            # "To: <email@domain.com>"
            r'To:\s*<([^>]+@[^>]+)>',
            
            # "To: email@domain.com"
            r'To:\s*([^\s<>\n]+@[^\s<>\n]+)',
            
            # "To: Name <email@domain.com>"
            r'To:\s*[^<\n]*<([^>]+@[^>]+)>',
            
            # Alternative: look for email in forwarded block with multiline support
            r'---------- Forwarded message ---------.*?To:\s*<([^>]+@[^>]+)>',
            
            # Gmail style: "To: email@domain.com"
            r'To:\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
            
            # More flexible pattern for any forwarded format
            r'(?:To|TO):\s*<?([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})>?',
        ]
        
        for i, pattern in enumerate(patterns):
            matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
            if matches:
                for match in matches:
                    email = match.strip()
                    logger.info(f"✅ Pattern {i+1} matched: {email}")
                    
                    # Validate email format
                    if PRParserService._is_valid_email(email):
                        logger.info(f"✅ Valid email found: {email}")
                        return email
                    else:
                        logger.warning(f"⚠️  Invalid email format: {email}")
        
        # ⭐ ADDITIONAL: Try HTML content if text failed
        if webhook_data.HtmlBody:
            html_email = PRParserService._extract_recipient_from_html(webhook_data.HtmlBody)
            if html_email:
                logger.info(f"✅ Found recipient in HTML: {html_email}")
                return html_email
        
        logger.warning(f"❌ Could not extract original recipient from content")
        return None
    
    @staticmethod
    def _extract_recipient_from_html(html_content: str) -> Optional[str]:
        """Extract recipient email from HTML content"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Look for "To:" in HTML
            text = soup.get_text()
            patterns = [
                r'To:\s*<([^>]+@[^>]+)>',
                r'To:\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    email = matches[0].strip()
                    if PRParserService._is_valid_email(email):
                        return email
            
        except Exception as e:
            logger.error(f"Error parsing HTML: {e}")
        
        return None
    
    @staticmethod
    def _is_valid_email(email: str) -> bool:
        """Basic email validation"""
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(email_pattern, email))
    
    @staticmethod
    def _is_forwarded_email(webhook_data: PostmarkInboundWebhook) -> bool:
        """Check if this is a forwarded Gmail message"""
        # Check subject for "Fwd:" prefix
        if webhook_data.Subject.startswith("Fwd:"):
            return True
        
        # Check if text body contains forwarded message indicators
        if webhook_data.TextBody:
            forwarded_indicators = [
                "---------- Forwarded message ---------",
                "Begin forwarded message:",
                "Forwarded message",
                "From:", "Date:", "Subject:", "To:"
            ]
            text_lower = webhook_data.TextBody.lower()
            forwarded_count = sum(1 for indicator in forwarded_indicators if indicator.lower() in text_lower)
            return forwarded_count >= 3
        
        return False
    
    @staticmethod
    def extract_pr_data(webhook_data: PostmarkInboundWebhook) -> PRExtractionResult:
        """Extract PR data from Postmark webhook payload"""
        try:
            logger.info(f"Parsing PR data from subject: {webhook_data.Subject}")
            
            # Check if this is a forwarded message
            is_forwarded = PRParserService._is_forwarded_email(webhook_data)
            
            # Extract original sender if forwarded
            original_sender = None
            if is_forwarded:
                original_sender = PRParserService._extract_original_sender(webhook_data)
            
            # Extract repo name from subject
            repo_name = PRParserService._extract_repo_name(webhook_data.Subject)
            
            # Extract PR title from subject
            pr_title = PRParserService._extract_pr_title(webhook_data.Subject)
            
            # Extract PR link from body
            pr_link = PRParserService._extract_pr_link(webhook_data.TextBody, webhook_data.HtmlBody)
            
            # Extract PR number
            pr_number = PRParserService._extract_pr_number(webhook_data.Subject, pr_link)
            
            # Determine PR status
            pr_status = PRParserService._extract_pr_status(webhook_data.Subject, webhook_data.TextBody)
            
            result = PRExtractionResult(
                repo_name=repo_name,
                pr_title=pr_title,
                pr_link=pr_link,
                pr_number=pr_number,
                pr_status=pr_status,
                is_forwarded=is_forwarded,
                original_sender=original_sender
            )
            
            logger.info(f"Extracted PR data: {result.model_dump()}")
            return result
            
        except Exception as e:
            logger.error(f"Error extracting PR data: {str(e)}")
            # Return minimal data even if parsing fails
            return PRExtractionResult(
                pr_title=webhook_data.Subject,
                is_forwarded=PRParserService._is_forwarded_email(webhook_data)
            )
    
    @staticmethod
    def _extract_original_sender(webhook_data: PostmarkInboundWebhook) -> Optional[str]:
        """Extract original sender from forwarded email"""
        if not webhook_data.TextBody:
            return None
        
        # Look for GitHub notifications email pattern
        github_pattern = r'From:\s*[^<]*<notifications@github\.com>'
        if re.search(github_pattern, webhook_data.TextBody):
            return "notifications@github.com"
        
        # Look for general From: pattern in forwarded message
        from_pattern = r'From:\s*([^\n<]+(?:<[^>]+>)?)'
        match = re.search(from_pattern, webhook_data.TextBody)
        if match:
            from_line = match.group(1).strip()
            # Extract email from "Name <email@domain.com>" format
            email_match = re.search(r'<([^>]+)>', from_line)
            if email_match:
                return email_match.group(1)
            return from_line
        
        return None
    
    @staticmethod
    def _extract_repo_name(subject: str) -> Optional[str]:
        """Extract repository name from subject line"""
        # Handle forwarded subjects - remove "Fwd: " prefix
        clean_subject = re.sub(r'^Fwd:\s*', '', subject, flags=re.IGNORECASE)
        
        # Look for [owner/repo] pattern
        repo_pattern = r'\[([^/\]]+/[^/\]]+)\]'
        match = re.search(repo_pattern, clean_subject)
        if match:
            return match.group(1)
        
        # Alternative pattern for GitHub notifications
        alt_pattern = r'(?:\[)?([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)(?:\])?'
        match = re.search(alt_pattern, clean_subject)
        if match and '/' in match.group(1):
            return match.group(1)
        
        return None
    
    @staticmethod
    def _extract_pr_title(subject: str) -> str:
        """Extract PR title from subject line"""
        # Handle forwarded subjects
        clean_subject = re.sub(r'^Fwd:\s*', '', subject, flags=re.IGNORECASE)
        
        # Remove [repo] prefix if present
        clean_subject = re.sub(r'^\[[^\]]+\]\s*', '', clean_subject)
        
        # Remove PR number suffix like "(PR #123)" or "(#123)"
        clean_subject = re.sub(r'\s*\((?:PR\s*)?#\d+\)$', '', clean_subject)
        
        # Clean up extra whitespace
        title = re.sub(r'\s+', ' ', clean_subject).strip()
        
        return title if title else "GitHub Notification"
    
    @staticmethod
    def _extract_pr_link(text_body: Optional[str], html_body: Optional[str]) -> Optional[str]:
        """Extract PR link from email body"""
        # Try HTML body first
        if html_body:
            soup = BeautifulSoup(html_body, 'html.parser')
            # Look for GitHub PR links
            links = soup.find_all('a', href=True)
            for link in links:
                href = link['href']
                if 'github.com' in href and '/pull/' in href:
                    # Clean the link (remove tracking parameters)
                    clean_link = re.sub(r'[?#].*$', '', href)
                    return clean_link
        
        # Fallback to text body
        if text_body:
            # Look for GitHub PR URLs
            url_patterns = [
                r'https://github\.com/[^/\s]+/[^/\s]+/pull/\d+',
                r'(?:View it on GitHub|Pull Request).*?(https://github\.com/[^/\s]+/[^/\s]+/pull/\d+)',
            ]
            
            for pattern in url_patterns:
                matches = re.findall(pattern, text_body, re.IGNORECASE)
                if matches:
                    # Return the first match, clean it up
                    link = matches[0] if isinstance(matches[0], str) else matches[0][-1]
                    return re.sub(r'[?#].*$', '', link)
        
        return None
    
    @staticmethod
    def _extract_pr_number(subject: str, pr_link: Optional[str]) -> Optional[str]:
        """Extract PR number from subject or link"""
        # First try subject line
        number_pattern = r'(?:PR\s*)?#(\d+)'
        match = re.search(number_pattern, subject, re.IGNORECASE)
        if match:
            return match.group(1)
        
        # Fallback to extracting from link
        if pr_link:
            link_pattern = r'/pull/(\d+)'
            match = re.search(link_pattern, pr_link)
            if match:
                return match.group(1)
        
        return None
    
    @staticmethod
    def _extract_pr_status(subject: str, text_body: Optional[str]) -> Optional[str]:
        """Extract PR status from content"""
        content = f"{subject} {text_body or ''}".lower()
        
        # Check for status keywords
        if any(word in content for word in ['merged', 'merge']):
            return 'merged'
        elif any(word in content for word in ['closed', 'close']):
            return 'closed'
        elif any(word in content for word in ['opened', 'open', 'new pull request']):
            return 'opened'
        elif any(word in content for word in ['updated', 'update']):
            return 'updated'
        
        return 'opened'  # Default status
    
    @staticmethod
    def create_slack_payload(
        extracted_data: PRExtractionResult,
        webhook_data: PostmarkInboundWebhook,
        user_name: Optional[str] = None
    ) -> SlackPayload:
        """Create Slack-ready payload for PR notification"""
        
        # Determine emoji based on PR status
        status_emoji = {
            'opened': '🔔',
            'merged': '✅',
            'closed': '❌',
            'updated': '🔄'
        }.get(extracted_data.pr_status or 'opened', '🔔')
        
        # Create main message
        repo_text = f"*{extracted_data.repo_name}*" if extracted_data.repo_name else "GitHub"
        pr_text = f"<{extracted_data.pr_link}|{extracted_data.pr_title}>" if extracted_data.pr_link else extracted_data.pr_title
        
        main_text = f"{status_emoji} {repo_text}: {pr_text}"
        
        if extracted_data.pr_number:
            main_text += f" (#{extracted_data.pr_number})"
        
        # Create attachment with details
        attachment = {
            "color": {
                'opened': '#28a745',
                'merged': '#6f42c1', 
                'closed': '#d73a49',
                'updated': '#0366d6'
            }.get(extracted_data.pr_status or 'opened', '#28a745'),
            "fields": [
                {
                    "title": "Repository",
                    "value": extracted_data.repo_name or "Unknown",
                    "short": True
                },
                {
                    "title": "Status",
                    "value": (extracted_data.pr_status or 'opened').title(),
                    "short": True
                }
            ],
            "footer": "GitHub PR Notification",
            "ts": int(datetime.now().timestamp())
        }
        
        # Add PR link as button if available
        if extracted_data.pr_link:
            attachment["actions"] = [
                {
                    "type": "button",
                    "text": "View PR",
                    "url": extracted_data.pr_link,
                    "style": "primary"
                }
            ]
        
        # Add forwarded indicator
        if extracted_data.is_forwarded:
            attachment["fields"].append({
                "title": "Source",
                "value": "📧 Forwarded Email",
                "short": True
            })
        
        return SlackPayload(
            text=main_text,
            attachments=[attachment]
        )
    
    @staticmethod
    def parse_date(date_string: str) -> datetime:
        """Parse Postmark date string to datetime object"""
        try:
            # Postmark typically sends dates in RFC 2822 format
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(date_string)
        except Exception as e:
            logger.warning(f"Could not parse date '{date_string}': {e}")
            return datetime.utcnow()# =============================================================================
# app/services/pr_perser_service.py (COMPLETE UPDATED VERSION)
# =============================================================================
import re
from typing import Optional, List, Dict, Any
from datetime import datetime
from bs4 import BeautifulSoup
from app.schemas.email import PostmarkInboundWebhook, PRExtractionResult, SlackPayload
from app.core.logger import get_module_logger

logger = get_module_logger(__name__, "logs/pr_parser.log")

class PRParserService:
    """Enhanced service for parsing GitHub PR notifications from Postmark webhooks"""
    
    @staticmethod
    def extract_recipient_email(webhook_data: PostmarkInboundWebhook) -> str:
        """
        Extract the actual user email from webhook data
        Handles both direct emails and forwarded emails
        """
        logger.info(f"🔍 Extracting recipient email from webhook")
        logger.info(f"📧 Webhook To: {webhook_data.OriginalRecipient}")
        logger.info(f"📧 Webhook From: {webhook_data.From}")
        logger.info(f"📧 Subject: {webhook_data.Subject}")
        
        # Check if this is a forwarded email
        is_forwarded = PRParserService._is_forwarded_email(webhook_data)
        logger.info(f"📤 Is forwarded email: {is_forwarded}")
        
        if is_forwarded:
            # ⭐ FOR FORWARDED EMAILS: Extract original recipient from email content
            original_recipient = PRParserService._extract_original_recipient_from_content(webhook_data)
            if original_recipient:
                logger.info(f"✅ Found original recipient in forwarded content: {original_recipient}")
                return original_recipient
            else:
                logger.warning(f"⚠️  Could not extract original recipient from forwarded content")
                # Fallback to webhook recipient
                return webhook_data.OriginalRecipient
        else:
            # ⭐ FOR DIRECT EMAILS: Use the webhook recipient
            logger.info(f"📨 Direct email, using webhook recipient: {webhook_data.OriginalRecipient}")
            return webhook_data.OriginalRecipient
    
    @staticmethod
    def _extract_original_recipient_from_content(webhook_data: PostmarkInboundWebhook) -> Optional[str]:
        """
        Extract the original 'To:' email from forwarded message content
        Looks for patterns like: "To: <email@domain.com>" or "To: email@domain.com"
        """
        content = webhook_data.TextBody or ""
        
        logger.debug(f"🔍 Searching for original recipient in content...")
        logger.debug(f"📄 Content preview: {content[:300]}...")
        
        # Common patterns for forwarded email "To:" lines
        patterns = [
            # "To: <email@domain.com>"
            r'To:\s*<([^>]+@[^>]+)>',
            
            # "To: email@domain.com"
            r'To:\s*([^\s<>\n]+@[^\s<>\n]+)',
            
            # "To: Name <email@domain.com>"
            r'To:\s*[^<\n]*<([^>]+@[^>]+)>',
            
            # Alternative: look for email in forwarded block with multiline support
            r'---------- Forwarded message ---------.*?To:\s*<([^>]+@[^>]+)>',
            
            # Gmail style: "To: email@domain.com"
            r'To:\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
            
            # More flexible pattern for any forwarded format
            r'(?:To|TO):\s*<?([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})>?',
        ]
        
        for i, pattern in enumerate(patterns):
            matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
            if matches:
                for match in matches:
                    email = match.strip()
                    logger.info(f"✅ Pattern {i+1} matched: {email}")
                    
                    # Validate email format
                    if PRParserService._is_valid_email(email):
                        logger.info(f"✅ Valid email found: {email}")
                        return email
                    else:
                        logger.warning(f"⚠️  Invalid email format: {email}")
        
        # ⭐ ADDITIONAL: Try HTML content if text failed
        if webhook_data.HtmlBody:
            html_email = PRParserService._extract_recipient_from_html(webhook_data.HtmlBody)
            if html_email:
                logger.info(f"✅ Found recipient in HTML: {html_email}")
                return html_email
        
        logger.warning(f"❌ Could not extract original recipient from content")
        return None
    
    @staticmethod
    def _extract_recipient_from_html(html_content: str) -> Optional[str]:
        """Extract recipient email from HTML content"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Look for "To:" in HTML
            text = soup.get_text()
            patterns = [
                r'To:\s*<([^>]+@[^>]+)>',
                r'To:\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    email = matches[0].strip()
                    if PRParserService._is_valid_email(email):
                        return email
            
        except Exception as e:
            logger.error(f"Error parsing HTML: {e}")
        
        return None
    
    @staticmethod
    def _is_valid_email(email: str) -> bool:
        """Basic email validation"""
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(email_pattern, email))
    
    @staticmethod
    def _is_forwarded_email(webhook_data: PostmarkInboundWebhook) -> bool:
        """Check if this is a forwarded Gmail message"""
        # Check subject for "Fwd:" prefix
        if webhook_data.Subject.startswith("Fwd:"):
            return True
        
        # Check if text body contains forwarded message indicators
        if webhook_data.TextBody:
            forwarded_indicators = [
                "---------- Forwarded message ---------",
                "Begin forwarded message:",
                "Forwarded message",
                "From:", "Date:", "Subject:", "To:"
            ]
            text_lower = webhook_data.TextBody.lower()
            forwarded_count = sum(1 for indicator in forwarded_indicators if indicator.lower() in text_lower)
            return forwarded_count >= 3
        
        return False
    
    @staticmethod
    def extract_pr_data(webhook_data: PostmarkInboundWebhook) -> PRExtractionResult:
        """Extract PR data from Postmark webhook payload"""
        try:
            logger.info(f"Parsing PR data from subject: {webhook_data.Subject}")
            
            # Check if this is a forwarded message
            is_forwarded = PRParserService._is_forwarded_email(webhook_data)
            
            # Extract original sender if forwarded
            original_sender = None
            if is_forwarded:
                original_sender = PRParserService._extract_original_sender(webhook_data)
            
            # Extract repo name from subject
            repo_name = PRParserService._extract_repo_name(webhook_data.Subject)
            
            # Extract PR title from subject
            pr_title = PRParserService._extract_pr_title(webhook_data.Subject)
            
            # Extract PR link from body
            pr_link = PRParserService._extract_pr_link(webhook_data.TextBody, webhook_data.HtmlBody)
            
            # Extract PR number
            pr_number = PRParserService._extract_pr_number(webhook_data.Subject, pr_link)
            
            # Determine PR status
            pr_status = PRParserService._extract_pr_status(webhook_data.Subject, webhook_data.TextBody)
            
            result = PRExtractionResult(
                repo_name=repo_name,
                pr_title=pr_title,
                pr_link=pr_link,
                pr_number=pr_number,
                pr_status=pr_status,
                is_forwarded=is_forwarded,
                original_sender=original_sender
            )
            
            logger.info(f"Extracted PR data: {result.model_dump()}")
            return result
            
        except Exception as e:
            logger.error(f"Error extracting PR data: {str(e)}")
            # Return minimal data even if parsing fails
            return PRExtractionResult(
                pr_title=webhook_data.Subject,
                is_forwarded=PRParserService._is_forwarded_email(webhook_data)
            )
    
    @staticmethod
    def _extract_original_sender(webhook_data: PostmarkInboundWebhook) -> Optional[str]:
        """Extract original sender from forwarded email"""
        if not webhook_data.TextBody:
            return None
        
        # Look for GitHub notifications email pattern
        github_pattern = r'From:\s*[^<]*<notifications@github\.com>'
        if re.search(github_pattern, webhook_data.TextBody):
            return "notifications@github.com"
        
        # Look for general From: pattern in forwarded message
        from_pattern = r'From:\s*([^\n<]+(?:<[^>]+>)?)'
        match = re.search(from_pattern, webhook_data.TextBody)
        if match:
            from_line = match.group(1).strip()
            # Extract email from "Name <email@domain.com>" format
            email_match = re.search(r'<([^>]+)>', from_line)
            if email_match:
                return email_match.group(1)
            return from_line
        
        return None
    
    @staticmethod
    def _extract_repo_name(subject: str) -> Optional[str]:
        """Extract repository name from subject line"""
        # Handle forwarded subjects - remove "Fwd: " prefix
        clean_subject = re.sub(r'^Fwd:\s*', '', subject, flags=re.IGNORECASE)
        
        # Look for [owner/repo] pattern
        repo_pattern = r'\[([^/\]]+/[^/\]]+)\]'
        match = re.search(repo_pattern, clean_subject)
        if match:
            return match.group(1)
        
        # Alternative pattern for GitHub notifications
        alt_pattern = r'(?:\[)?([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)(?:\])?'
        match = re.search(alt_pattern, clean_subject)
        if match and '/' in match.group(1):
            return match.group(1)
        
        return None
    
    @staticmethod
    def _extract_pr_title(subject: str) -> str:
        """Extract PR title from subject line"""
        # Handle forwarded subjects
        clean_subject = re.sub(r'^Fwd:\s*', '', subject, flags=re.IGNORECASE)
        
        # Remove [repo] prefix if present
        clean_subject = re.sub(r'^\[[^\]]+\]\s*', '', clean_subject)
        
        # Remove PR number suffix like "(PR #123)" or "(#123)"
        clean_subject = re.sub(r'\s*\((?:PR\s*)?#\d+\)$', '', clean_subject)
        
        # Clean up extra whitespace
        title = re.sub(r'\s+', ' ', clean_subject).strip()
        
        return title if title else "GitHub Notification"
    
    @staticmethod
    def _extract_pr_link(text_body: Optional[str], html_body: Optional[str]) -> Optional[str]:
        """Extract PR link from email body"""
        # Try HTML body first
        if html_body:
            soup = BeautifulSoup(html_body, 'html.parser')
            # Look for GitHub PR links
            links = soup.find_all('a', href=True)
            for link in links:
                href = link['href']
                if 'github.com' in href and '/pull/' in href:
                    # Clean the link (remove tracking parameters)
                    clean_link = re.sub(r'[?#].*$', '', href)
                    return clean_link
        
        # Fallback to text body
        if text_body:
            # Look for GitHub PR URLs
            url_patterns = [
                r'https://github\.com/[^/\s]+/[^/\s]+/pull/\d+',
                r'(?:View it on GitHub|Pull Request).*?(https://github\.com/[^/\s]+/[^/\s]+/pull/\d+)',
            ]
            
            for pattern in url_patterns:
                matches = re.findall(pattern, text_body, re.IGNORECASE)
                if matches:
                    # Return the first match, clean it up
                    link = matches[0] if isinstance(matches[0], str) else matches[0][-1]
                    return re.sub(r'[?#].*$', '', link)
        
        return None
    
    @staticmethod
    def _extract_pr_number(subject: str, pr_link: Optional[str]) -> Optional[str]:
        """Extract PR number from subject or link"""
        # First try subject line
        number_pattern = r'(?:PR\s*)?#(\d+)'
        match = re.search(number_pattern, subject, re.IGNORECASE)
        if match:
            return match.group(1)
        
        # Fallback to extracting from link
        if pr_link:
            link_pattern = r'/pull/(\d+)'
            match = re.search(link_pattern, pr_link)
            if match:
                return match.group(1)
        
        return None
    
    @staticmethod
    def _extract_pr_status(subject: str, text_body: Optional[str]) -> Optional[str]:
        """Extract PR status from content"""
        content = f"{subject} {text_body or ''}".lower()
        
        # Check for status keywords
        if any(word in content for word in ['merged', 'merge']):
            return 'merged'
        elif any(word in content for word in ['closed', 'close']):
            return 'closed'
        elif any(word in content for word in ['opened', 'open', 'new pull request']):
            return 'opened'
        elif any(word in content for word in ['updated', 'update']):
            return 'updated'
        
        return 'opened'  # Default status
    
    @staticmethod
    def create_slack_payload(
        extracted_data: PRExtractionResult,
        webhook_data: PostmarkInboundWebhook,
        user_name: Optional[str] = None
    ) -> SlackPayload:
        """Create Slack-ready payload for PR notification"""
        
        # Determine emoji based on PR status
        status_emoji = {
            'opened': '🔔',
            'merged': '✅',
            'closed': '❌',
            'updated': '🔄'
        }.get(extracted_data.pr_status or 'opened', '🔔')
        
        # Create main message
        repo_text = f"*{extracted_data.repo_name}*" if extracted_data.repo_name else "GitHub"
        pr_text = f"<{extracted_data.pr_link}|{extracted_data.pr_title}>" if extracted_data.pr_link else extracted_data.pr_title
        
        main_text = f"{status_emoji} {repo_text}: {pr_text}"
        
        if extracted_data.pr_number:
            main_text += f" (#{extracted_data.pr_number})"
        
        # Create attachment with details
        attachment = {
            "color": {
                'opened': '#28a745',
                'merged': '#6f42c1', 
                'closed': '#d73a49',
                'updated': '#0366d6'
            }.get(extracted_data.pr_status or 'opened', '#28a745'),
            "fields": [
                {
                    "title": "Repository",
                    "value": extracted_data.repo_name or "Unknown",
                    "short": True
                },
                {
                    "title": "Status",
                    "value": (extracted_data.pr_status or 'opened').title(),
                    "short": True
                }
            ],
            "footer": "GitHub PR Notification",
            "ts": int(datetime.now().timestamp())
        }
        
        # Add PR link as button if available
        if extracted_data.pr_link:
            attachment["actions"] = [
                {
                    "type": "button",
                    "text": "View PR",
                    "url": extracted_data.pr_link,
                    "style": "primary"
                }
            ]
        
        # Add forwarded indicator
        if extracted_data.is_forwarded:
            attachment["fields"].append({
                "title": "Source",
                "value": "📧 Forwarded Email",
                "short": True
            })
        
        return SlackPayload(
            text=main_text,
            attachments=[attachment]
        )
    
    @staticmethod
    def parse_date(date_string: str) -> datetime:
        """Parse Postmark date string to datetime object"""
        try:
            # Postmark typically sends dates in RFC 2822 format
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(date_string)
        except Exception as e:
            logger.warning(f"Could not parse date '{date_string}': {e}")
            return datetime.utcnow()