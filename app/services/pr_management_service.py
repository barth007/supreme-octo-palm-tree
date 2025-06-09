# app/services/pr_management_service.py (FIXED UUID handling)
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc, asc, text
from datetime import datetime, timedelta
from collections import defaultdict
import math
import uuid

from app.models.pr_notification import PullRequestNotification
from app.models.user import User
from app.schemas.pr_management import (
    PRNotificationResponse, 
    PRNotificationList, 
    PRNotificationSummary,
    PRFilterParams,
    PRStatsResponse,
    PRSummaryResponse
)
from app.core.logger import get_module_logger

logger = get_module_logger(__name__, "logs/pr_management_service.log")

class PRManagementService:
    """Enhanced service for managing PR notifications with advanced filtering and analytics"""

    @staticmethod
    def get_user_pr_notifications(
        db: Session, 
        user_id: str, 
        filters: PRFilterParams
    ) -> PRNotificationList:
        """
        Get paginated and filtered PR notifications for a user
        """
        try:
            # 🔧 FIX: Convert string user_id to UUID properly
            try:
                if isinstance(user_id, str):
                    user_uuid = uuid.UUID(user_id)
                else:
                    user_uuid = user_id
            except ValueError as e:
                logger.error(f"Invalid user_id format: {user_id}")
                raise ValueError(f"Invalid user_id format: {user_id}")
            
            logger.info(f"Getting PR notifications for user: {user_uuid}")
            
            # Base query with proper UUID
            query = db.query(PullRequestNotification).filter(
                PullRequestNotification.user_id == user_uuid
            )
            
            # Apply filters
            query = PRManagementService._apply_filters(query, filters)
            
            # Get total count before pagination
            total_count = query.count()
            logger.info(f"Total notifications found: {total_count}")
            
            # Apply sorting
            query = PRManagementService._apply_sorting(query, filters)
            
            # Apply pagination
            offset = (filters.page - 1) * filters.limit
            notifications = query.offset(offset).limit(filters.limit).all()
            
            logger.info(f"Retrieved {len(notifications)} notifications for page {filters.page}")
            
            # Convert to summary format
            notification_summaries = [
                PRNotificationSummary(
                    id=str(n.id),
                    repo_name=n.repo_name,
                    pr_title=n.pr_title,
                    pr_link=n.pr_link,
                    pr_number=n.pr_number,
                    pr_status=n.pr_status,
                    received_at=n.received_at,
                    slack_sent=n.slack_sent,
                    is_forwarded=n.is_forwarded
                ) for n in notifications
            ]
            
            # Calculate pagination info
            total_pages = math.ceil(total_count / filters.limit) if total_count > 0 else 1
            has_next = filters.page < total_pages
            has_previous = filters.page > 1
            
            logger.info(f"Pagination: page {filters.page}/{total_pages}, has_next: {has_next}")
            
            return PRNotificationList(
                notifications=notification_summaries,
                total_count=total_count,
                page=filters.page,
                limit=filters.limit,
                total_pages=total_pages,
                has_next=has_next,
                has_previous=has_previous
            )
            
        except Exception as e:
            logger.error(f"Error retrieving PR notifications: {str(e)}")
            raise e

    @staticmethod
    def _apply_filters(query, filters: PRFilterParams):
        """Apply filtering conditions to the query"""
        
        # Status filter
        if filters.status:
            query = query.filter(PullRequestNotification.pr_status == filters.status)
            logger.debug(f"Applied status filter: {filters.status}")
        
        # Repository filter
        if filters.repo_name:
            query = query.filter(PullRequestNotification.repo_name.ilike(f"%{filters.repo_name}%"))
            logger.debug(f"Applied repo filter: {filters.repo_name}")
        
        # Days old filter
        if filters.days_old:
            cutoff_date = datetime.utcnow() - timedelta(days=filters.days_old)
            query = query.filter(PullRequestNotification.received_at <= cutoff_date)
            logger.debug(f"Applied days_old filter: {filters.days_old} (cutoff: {cutoff_date})")
        
        # Slack sent filter
        if filters.slack_sent is not None:
            query = query.filter(PullRequestNotification.slack_sent == filters.slack_sent)
            logger.debug(f"Applied slack_sent filter: {filters.slack_sent}")
        
        # Forwarded email filter
        if filters.is_forwarded is not None:
            query = query.filter(PullRequestNotification.is_forwarded == filters.is_forwarded)
            logger.debug(f"Applied is_forwarded filter: {filters.is_forwarded}")
        
        return query

    @staticmethod
    def _apply_sorting(query, filters: PRFilterParams):
        """Apply sorting to the query"""
        sort_column = getattr(PullRequestNotification, filters.sort_by, None)
        
        if not sort_column:
            sort_column = PullRequestNotification.received_at
            logger.debug(f"Invalid sort_by field '{filters.sort_by}', using 'received_at'")
        
        if filters.sort_order == "asc":
            query = query.order_by(asc(sort_column))
        else:
            query = query.order_by(desc(sort_column))
        
        logger.debug(f"Applied sorting: {filters.sort_by} {filters.sort_order}")
        return query

    @staticmethod
    def get_pr_notification_by_id(
        db: Session, 
        notification_id: str, 
        user_id: str
    ) -> Optional[PRNotificationResponse]:
        """Get a specific PR notification by ID (with user ownership check)"""
        try:
            # Convert IDs to UUIDs
            try:
                notification_uuid = uuid.UUID(notification_id)
                user_uuid = uuid.UUID(user_id)
            except ValueError:
                logger.error(f"Invalid UUID format: notification_id={notification_id}, user_id={user_id}")
                return None
            
            notification = db.query(PullRequestNotification).filter(
                and_(
                    PullRequestNotification.id == notification_uuid,
                    PullRequestNotification.user_id == user_uuid
                )
            ).first()
            
            if not notification:
                return None
            
            return PRNotificationResponse(
                id=str(notification.id),
                user_id=str(notification.user_id),
                sender_email=notification.sender_email,
                recipient_email=notification.recipient_email,
                repo_name=notification.repo_name,
                pr_title=notification.pr_title,
                pr_link=notification.pr_link,
                subject=notification.subject,
                received_at=notification.received_at,
                message_id=notification.message_id,
                raw_text=notification.raw_text,
                raw_html=notification.raw_html,
                slack_sent=notification.slack_sent,
                pr_number=notification.pr_number,
                pr_status=notification.pr_status,
                is_forwarded=notification.is_forwarded,
                created_at=notification.created_at,
                updated_at=notification.updated_at
            )
            
        except Exception as e:
            logger.error(f"Error retrieving PR notification {notification_id}: {str(e)}")
            return None

    @staticmethod
    def delete_pr_notification(
        db: Session, 
        notification_id: str, 
        user_id: str
    ) -> bool:
        """Delete a PR notification (with user ownership check)"""
        try:
            # Convert IDs to UUIDs
            try:
                notification_uuid = uuid.UUID(notification_id)
                user_uuid = uuid.UUID(user_id)
            except ValueError:
                logger.error(f"Invalid UUID format: notification_id={notification_id}, user_id={user_id}")
                return False
            
            notification = db.query(PullRequestNotification).filter(
                and_(
                    PullRequestNotification.id == notification_uuid,
                    PullRequestNotification.user_id == user_uuid
                )
            ).first()
            
            if not notification:
                return False
            
            db.delete(notification)
            db.commit()
            logger.info(f"Deleted PR notification: {notification_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting PR notification {notification_id}: {str(e)}")
            db.rollback()
            return False

    @staticmethod
    def get_user_pr_stats(db: Session, user_id: str) -> PRStatsResponse:
        """Get comprehensive PR statistics for a user"""
        try:
            # Convert user_id to UUID
            try:
                user_uuid = uuid.UUID(user_id)
            except ValueError:
                logger.error(f"Invalid user_id format: {user_id}")
                return PRStatsResponse(
                    total_notifications=0,
                    slack_sent=0,
                    pending_slack=0,
                    by_status={},
                    by_repository={},
                    forwarded_emails=0,
                    recent_activity={}
                )
            
            # Base query for user's notifications
            base_query = db.query(PullRequestNotification).filter(
                PullRequestNotification.user_id == user_uuid
            )
            
            # Total counts
            total_notifications = base_query.count()
            slack_sent = base_query.filter(PullRequestNotification.slack_sent == True).count()
            pending_slack = total_notifications - slack_sent
            forwarded_emails = base_query.filter(PullRequestNotification.is_forwarded == True).count()
            
            # Status breakdown
            status_stats = {}
            for status in ['opened', 'merged', 'closed']:
                count = base_query.filter(PullRequestNotification.pr_status == status).count()
                status_stats[status] = count
            
            # Repository breakdown (top 10)
            repo_stats = db.query(
                PullRequestNotification.repo_name,
                func.count(PullRequestNotification.id).label('count')
            ).filter(
                PullRequestNotification.user_id == user_uuid,
                PullRequestNotification.repo_name.is_not(None)
            ).group_by(
                PullRequestNotification.repo_name
            ).order_by(
                desc('count')
            ).limit(10).all()
            
            repo_dict = {repo.repo_name: repo.count for repo in repo_stats}
            
            # Recent activity (last 7 days)
            seven_days_ago = datetime.utcnow() - timedelta(days=7)
            recent_stats = {}
            for i in range(7):
                date = seven_days_ago + timedelta(days=i)
                date_str = date.strftime('%Y-%m-%d')
                
                count = base_query.filter(
                    func.date(PullRequestNotification.received_at) == date.date()
                ).count()
                recent_stats[date_str] = count
            
            # Additional insights
            oldest_pending = base_query.filter(
                PullRequestNotification.slack_sent == False
            ).order_by(asc(PullRequestNotification.received_at)).first()
            
            newest_pr = base_query.order_by(
                desc(PullRequestNotification.received_at)
            ).first()
            
            most_active_repo = repo_stats[0].repo_name if repo_stats else None
            
            return PRStatsResponse(
                total_notifications=total_notifications,
                slack_sent=slack_sent,
                pending_slack=pending_slack,
                by_status=status_stats,
                by_repository=repo_dict,
                forwarded_emails=forwarded_emails,
                recent_activity=recent_stats,
                oldest_pending_pr=oldest_pending.received_at if oldest_pending else None,
                newest_pr=newest_pr.received_at if newest_pr else None,
                most_active_repo=most_active_repo
            )
            
        except Exception as e:
            logger.error(f"Error getting PR stats: {str(e)}")
            return PRStatsResponse(
                total_notifications=0,
                slack_sent=0,
                pending_slack=0,
                by_status={},
                by_repository={},
                forwarded_emails=0,
                recent_activity={}
            )

    @staticmethod
    def mark_slack_sent(db: Session, notification_id: str, user_id: str) -> bool:
        """Mark a notification as sent to Slack (with user ownership check)"""
        try:
            # Convert IDs to UUIDs
            try:
                notification_uuid = uuid.UUID(notification_id)
                user_uuid = uuid.UUID(user_id)
            except ValueError:
                logger.error(f"Invalid UUID format: notification_id={notification_id}, user_id={user_id}")
                return False
            
            notification = db.query(PullRequestNotification).filter(
                and_(
                    PullRequestNotification.id == notification_uuid,
                    PullRequestNotification.user_id == user_uuid
                )
            ).first()
            
            if not notification:
                return False
            
            notification.slack_sent = True
            db.commit()
            logger.info(f"Marked notification {notification_id} as Slack sent")
            return True
            
        except Exception as e:
            logger.error(f"Error marking notification as Slack sent: {str(e)}")
            db.rollback()
            return False

    # Add other methods with similar UUID handling...
    @staticmethod
    def get_user_repositories(db: Session, user_id: str) -> List[str]:
        """Get list of unique repositories for a user"""
        try:
            # Convert user_id to UUID
            try:
                user_uuid = uuid.UUID(user_id)
            except ValueError:
                logger.error(f"Invalid user_id format: {user_id}")
                return []
            
            repositories = db.query(PullRequestNotification.repo_name).filter(
                and_(
                    PullRequestNotification.user_id == user_uuid,
                    PullRequestNotification.repo_name.is_not(None)
                )
            ).distinct().order_by(PullRequestNotification.repo_name).all()
            
            return [repo[0] for repo in repositories]
            
        except Exception as e:
            logger.error(f"Error getting user repositories: {str(e)}")
            return []