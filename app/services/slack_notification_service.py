# =============================================================================
# app/services/slack_notification_service.py
# =============================================================================
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import requests
import json
from app.models.slack_connection import SlackConnection
from app.models.pr_notification import PullRequestNotification
from app.models.user import User
from app.core.logger import get_module_logger

logger = get_module_logger(__name__, "logs/slack_notifications.log")

class SlackNotificationService:
    """Enhanced service for sending Slack notifications about PR reminders"""
    
    SLACK_API_BASE = "https://slack.com/api"
    
    @staticmethod
    def send_pr_reminder_notification(
        access_token: str,
        slack_user_id: str,
        user_name: str,
        pr_notification: PullRequestNotification
    ) -> Dict[str, Any]:
        """
        Send a formatted PR reminder message to Slack
        """
        try:
            # Calculate how many days ago the PR was received
            days_ago = (datetime.utcnow() - pr_notification.received_at).days
            
            # Create the main message text
            main_text = f"👋 Hey {user_name}, you have an open PR that needs attention!"
            
            # Create rich message blocks
            blocks = SlackNotificationService._create_pr_reminder_blocks(
                pr_notification, days_ago, user_name
            )
            
            # Send the message
            result = SlackNotificationService._send_slack_message(
                access_token=access_token,
                channel=slack_user_id,  # Send as DM
                text=main_text,
                blocks=blocks
            )
            
            if result.get("success"):
                logger.info(f"Successfully sent PR reminder for PR: {pr_notification.pr_title}")
            else:
                logger.error(f"Failed to send PR reminder: {result.get('error')}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error sending PR reminder notification: {str(e)}")
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def send_bulk_pr_reminders(
        access_token: str,
        slack_user_id: str,
        user_name: str,
        pr_notifications: List[PullRequestNotification]
    ) -> Dict[str, Any]:
        """
        Send a single message with multiple PR reminders
        """
        try:
            if not pr_notifications:
                return {"success": True, "message": "No PRs to remind about"}
            
            # Group PRs by age for better organization
            pr_groups = SlackNotificationService._group_prs_by_age(pr_notifications)
            
            # Create the main message text
            total_prs = len(pr_notifications)
            main_text = f"👋 Hey {user_name}, you have {total_prs} open PR{'s' if total_prs > 1 else ''} that need{'s' if total_prs == 1 else ''} attention!"
            
            # Create rich message blocks for bulk reminder
            blocks = SlackNotificationService._create_bulk_reminder_blocks(
                pr_groups, user_name
            )
            
            # Send the message
            result = SlackNotificationService._send_slack_message(
                access_token=access_token,
                channel=slack_user_id,
                text=main_text,
                blocks=blocks
            )
            
            if result.get("success"):
                logger.info(f"Successfully sent bulk PR reminder for {total_prs} PRs")
            else:
                logger.error(f"Failed to send bulk PR reminder: {result.get('error')}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error sending bulk PR reminders: {str(e)}")
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def send_daily_summary(
        access_token: str,
        slack_user_id: str,
        user_name: str,
        summary_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Send a daily summary of PR activity
        """
        try:
            main_text = f"📊 Good morning {user_name}! Here's your PR summary for today:"
            
            blocks = SlackNotificationService._create_daily_summary_blocks(
                summary_data, user_name
            )
            
            result = SlackNotificationService._send_slack_message(
                access_token=access_token,
                channel=slack_user_id,
                text=main_text,
                blocks=blocks
            )
            
            if result.get("success"):
                logger.info(f"Successfully sent daily summary to {user_name}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error sending daily summary: {str(e)}")
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def _send_slack_message(
        access_token: str,
        channel: str,
        text: str,
        blocks: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Send message to Slack using the chat.postMessage API
        """
        url = f"{SlackNotificationService.SLACK_API_BASE}/chat.postMessage"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "channel": channel,
            "text": text,
            "unfurl_links": False,
            "unfurl_media": False
        }
        
        if blocks:
            payload["blocks"] = blocks
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            response_data = response.json()
            
            if response_data.get("ok"):
                return {
                    "success": True,
                    "data": response_data,
                    "message_ts": response_data.get("ts")
                }
            else:
                error_msg = response_data.get("error", "Unknown Slack API error")
                logger.error(f"Slack API error: {error_msg}")
                return {"success": False, "error": error_msg}
                
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Slack API timeout"}
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": f"Request failed: {str(e)}"}
        except Exception as e:
            return {"success": False, "error": f"Unexpected error: {str(e)}"}
    
    @staticmethod
    def _create_pr_reminder_blocks(
        pr_notification: PullRequestNotification,
        days_ago: int,
        user_name: str
    ) -> List[Dict]:
        """
        Create Slack blocks for a single PR reminder
        """
        # Choose emoji based on urgency
        urgency_emoji = "🟢" if days_ago <= 2 else "🟡" if days_ago <= 5 else "🔴"
        urgency_text = "New" if days_ago <= 1 else "Getting old" if days_ago <= 5 else "URGENT"
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{urgency_emoji} PR Reminder - {urgency_text}"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Repository:*\n{pr_notification.repo_name or 'Unknown'}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Age:*\n{days_ago} day{'s' if days_ago != 1 else ''} ago"
                    }
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*PR Title:*\n{pr_notification.pr_title}"
                }
            }
        ]
        
        # Add action buttons if PR link is available
        if pr_notification.pr_link:
            blocks.append({
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "🔗 View PR"
                        },
                        "url": pr_notification.pr_link,
                        "style": "primary"
                    }
                ]
            })
        
        # Add motivational footer
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "Let's keep things moving! 🚀 Your team is counting on you!"
                }
            ]
        })
        
        return blocks
    
    @staticmethod
    def _create_bulk_reminder_blocks(
        pr_groups: Dict[str, List[PullRequestNotification]],
        user_name: str
    ) -> List[Dict]:
        """
        Create Slack blocks for bulk PR reminders
        """
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "📋 Your Open PRs Summary"
                }
            }
        ]
        
        # Add sections for each age group
        for age_group, prs in pr_groups.items():
            if not prs:
                continue
            
            # Determine emoji and urgency
            if "urgent" in age_group.lower():
                emoji = "🔴"
                style = "danger"
            elif "old" in age_group.lower():
                emoji = "🟡"
                style = "warning"
            else:
                emoji = "🟢"
                style = "primary"
            
            # Group header
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{emoji} {age_group} ({len(prs)} PR{'s' if len(prs) > 1 else ''})*"
                }
            })
            
            # List PRs in this group (limit to 5 per group)
            for pr in prs[:5]:
                days_ago = (datetime.utcnow() - pr.received_at).days
                pr_text = f"• *{pr.repo_name or 'Unknown'}*: {pr.pr_title[:50]}{'...' if len(pr.pr_title) > 50 else ''}"
                
                if pr.pr_link:
                    pr_text = f"• *{pr.repo_name or 'Unknown'}*: <{pr.pr_link}|{pr.pr_title[:50]}{'...' if len(pr.pr_title) > 50 else ''}>"
                
                pr_text += f" _{days_ago}d ago_"
                
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": pr_text
                    }
                })
            
            # Show "and X more" if there are more PRs
            if len(prs) > 5:
                blocks.append({
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"_...and {len(prs) - 5} more in this category_"
                        }
                    ]
                })
            
            # Add divider between groups
            blocks.append({"type": "divider"})
        
        # Add motivational footer
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "🎯 *Ready to tackle these PRs?* Your team will appreciate the quick reviews! 🚀"
            }
        })
        
        return blocks
    
    @staticmethod
    def _create_daily_summary_blocks(
        summary_data: Dict[str, Any],
        user_name: str
    ) -> List[Dict]:
        """
        Create Slack blocks for daily summary
        """
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "📊 Your Daily PR Summary"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Total Open PRs:*\n{summary_data.get('total_open', 0)}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*New Today:*\n{summary_data.get('new_today', 0)}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Needs Attention:*\n{summary_data.get('needs_attention', 0)}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Most Active Repo:*\n{summary_data.get('most_active_repo', 'None')}"
                    }
                ]
            }
        ]
        
        # Add action items if any
        action_items = summary_data.get('action_items', [])
        if action_items:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*🎯 Today's Action Items:*\n" + "\n".join([f"• {item}" for item in action_items[:3]])
                }
            })
        
        # Add motivational message
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "Have a productive day! 💪"
                }
            ]
        })
        
        return blocks
    
    @staticmethod
    def _group_prs_by_age(
        pr_notifications: List[PullRequestNotification]
    ) -> Dict[str, List[PullRequestNotification]]:
        """
        Group PRs by their age for better organization
        """
        groups = {
            "🟢 Recent (1-2 days)": [],
            "🟡 Getting Old (3-7 days)": [],
            "🔴 Urgent (8+ days)": []
        }
        
        now = datetime.utcnow()
        
        for pr in pr_notifications:
            days_ago = (now - pr.received_at).days
            
            if days_ago <= 2:
                groups["🟢 Recent (1-2 days)"].append(pr)
            elif days_ago <= 7:
                groups["🟡 Getting Old (3-7 days)"].append(pr)
            else:
                groups["🔴 Urgent (8+ days)"].append(pr)
        
        # Remove empty groups
        return {k: v for k, v in groups.items() if v}
    
    @staticmethod
    def test_slack_connection(access_token: str, slack_user_id: str) -> Dict[str, Any]:
        """
        Test Slack connection by sending a simple test message
        """
        test_message = "🧪 Test message from your PR notification system! Connection is working perfectly. 🎉"
        
        return SlackNotificationService._send_slack_message(
            access_token=access_token,
            channel=slack_user_id,
            text=test_message
        )