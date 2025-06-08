# =============================================================================
# app/services/pr_management_service.py
# =============================================================================
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc, asc, text
from datetime import datetime, timedelta
from collections import defaultdict
import math

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
            # Base query
            query = db.query(PullRequestNotification).filter(
                PullRequestNotification.user_id == user_id
            )
            
            # Apply filters
            query = PRManagementService._apply_filters(query, filters)
            
            # Get total count before pagination
            total_count = query.count()
            
            # Apply sorting
            query = PRManagementService._apply_sorting(query, filters)
            
            # Apply pagination
            offset = (filters.page - 1) * filters.limit
            notifications = query.offset(offset).limit(filters.limit).all()
            
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
            total_pages = math.ceil(total_count / filters.limit)
            has_next = filters.page < total_pages
            has_previous = filters.page > 1
            
            logger.info(f"Retrieved {len(notifications)} notifications (page {filters.page}/{total_pages})")
            
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
        
        # Repository filter
        if filters.repo_name:
            query = query.filter(PullRequestNotification.repo_name.ilike(f"%{filters.repo_name}%"))
        
        # Days old filter
        if filters.days_old:
            cutoff_date = datetime.utcnow() - timedelta(days=filters.days_old)
            query = query.filter(PullRequestNotification.received_at <= cutoff_date)
        
        # Slack sent filter
        if filters.slack_sent is not None:
            query = query.filter(PullRequestNotification.slack_sent == filters.slack_sent)
        
        # Forwarded email filter
        if filters.is_forwarded is not None:
            query = query.filter(PullRequestNotification.is_forwarded == filters.is_forwarded)
        
        return query

    @staticmethod
    def _apply_sorting(query, filters: PRFilterParams):
        """Apply sorting to the query"""
        sort_column = getattr(PullRequestNotification, filters.sort_by, None)
        
        if not sort_column:
            sort_column = PullRequestNotification.received_at
        
        if filters.sort_order == "asc":
            query = query.order_by(asc(sort_column))
        else:
            query = query.order_by(desc(sort_column))
        
        return query

    @staticmethod
    def get_pr_notification_by_id(
        db: Session, 
        notification_id: str, 
        user_id: str
    ) -> Optional[PRNotificationResponse]:
        """Get a specific PR notification by ID (with user ownership check)"""
        try:
            notification = db.query(PullRequestNotification).filter(
                and_(
                    PullRequestNotification.id == notification_id,
                    PullRequestNotification.user_id == user_id
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
            notification = db.query(PullRequestNotification).filter(
                and_(
                    PullRequestNotification.id == notification_id,
                    PullRequestNotification.user_id == user_id
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
            # Base query for user's notifications
            base_query = db.query(PullRequestNotification).filter(
                PullRequestNotification.user_id == user_id
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
                PullRequestNotification.user_id == user_id,
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
    def get_pr_summary(db: Session, user_id: str, days: int) -> PRSummaryResponse:
        """Get PR activity summary for a specific time period"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Base query for the time period
            period_query = db.query(PullRequestNotification).filter(
                and_(
                    PullRequestNotification.user_id == user_id,
                    PullRequestNotification.received_at >= cutoff_date
                )
            )
            
            total_notifications = period_query.count()
            
            # Status counts
            new_prs = period_query.filter(PullRequestNotification.pr_status == 'opened').count()
            merged_prs = period_query.filter(PullRequestNotification.pr_status == 'merged').count()
            closed_prs = period_query.filter(PullRequestNotification.pr_status == 'closed').count()
            
            # Repositories involved
            repositories = db.query(PullRequestNotification.repo_name).filter(
                and_(
                    PullRequestNotification.user_id == user_id,
                    PullRequestNotification.received_at >= cutoff_date,
                    PullRequestNotification.repo_name.is_not(None)
                )
            ).distinct().all()
            
            repo_list = [repo[0] for repo in repositories]
            
            # Daily activity
            daily_activity = {}
            for i in range(days):
                date = cutoff_date + timedelta(days=i)
                date_str = date.strftime('%Y-%m-%d')
                
                count = period_query.filter(
                    func.date(PullRequestNotification.received_at) == date.date()
                ).count()
                daily_activity[date_str] = count
            
            # Actionable insights
            pending_reviews = db.query(PullRequestNotification).filter(
                and_(
                    PullRequestNotification.user_id == user_id,
                    PullRequestNotification.pr_status == 'opened',
                    PullRequestNotification.slack_sent == False
                )
            ).count()
            
            old_threshold = datetime.utcnow() - timedelta(days=7)
            old_open_prs = db.query(PullRequestNotification).filter(
                and_(
                    PullRequestNotification.user_id == user_id,
                    PullRequestNotification.pr_status == 'opened',
                    PullRequestNotification.received_at <= old_threshold
                )
            ).count()
            
            notification_rate = total_notifications / days if days > 0 else 0
            
            return PRSummaryResponse(
                period_days=days,
                total_notifications=total_notifications,
                new_prs=new_prs,
                merged_prs=merged_prs,
                closed_prs=closed_prs,
                repositories_involved=repo_list,
                daily_activity=daily_activity,
                pending_reviews=pending_reviews,
                old_open_prs=old_open_prs,
                notification_rate=round(notification_rate, 2)
            )
            
        except Exception as e:
            logger.error(f"Error getting PR summary: {str(e)}")
            return PRSummaryResponse(
                period_days=days,
                total_notifications=0,
                new_prs=0,
                merged_prs=0,
                closed_prs=0,
                repositories_involved=[],
                daily_activity={},
                pending_reviews=0,
                old_open_prs=0,
                notification_rate=0.0
            )

    @staticmethod
    def get_user_repositories(db: Session, user_id: str) -> List[str]:
        """Get list of unique repositories for a user"""
        try:
            repositories = db.query(PullRequestNotification.repo_name).filter(
                and_(
                    PullRequestNotification.user_id == user_id,
                    PullRequestNotification.repo_name.is_not(None)
                )
            ).distinct().order_by(PullRequestNotification.repo_name).all()
            
            return [repo[0] for repo in repositories]
            
        except Exception as e:
            logger.error(f"Error getting user repositories: {str(e)}")
            return []

    @staticmethod
    def mark_slack_sent(db: Session, notification_id: str, user_id: str) -> bool:
        """Mark a notification as sent to Slack (with user ownership check)"""
        try:
            notification = db.query(PullRequestNotification).filter(
                and_(
                    PullRequestNotification.id == notification_id,
                    PullRequestNotification.user_id == user_id
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

    @staticmethod
    def bulk_delete_notifications(
        db: Session, 
        notification_ids: List[str], 
        user_id: str
    ) -> Dict[str, Any]:
        """Bulk delete PR notifications"""
        try:
            deleted_count = 0
            failed_ids = []
            
            for notification_id in notification_ids:
                notification = db.query(PullRequestNotification).filter(
                    and_(
                        PullRequestNotification.id == notification_id,
                        PullRequestNotification.user_id == user_id
                    )
                ).first()
                
                if notification:
                    db.delete(notification)
                    deleted_count += 1
                else:
                    failed_ids.append(notification_id)
            
            db.commit()
            
            result = {
                "success": True,
                "deleted_count": deleted_count,
                "failed_count": len(failed_ids),
                "failed_ids": failed_ids
            }
            
            logger.info(f"Bulk deleted {deleted_count} notifications for user {user_id}")
            return result
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error in bulk delete: {str(e)}")
            return {
                "success": False,
                "deleted_count": 0,
                "failed_count": len(notification_ids),
                "error": str(e)
            }

    @staticmethod
    def bulk_mark_slack_sent(
        db: Session, 
        notification_ids: List[str], 
        user_id: str
    ) -> Dict[str, Any]:
        """Bulk mark notifications as Slack sent"""
        try:
            updated_count = 0
            failed_ids = []
            
            for notification_id in notification_ids:
                notification = db.query(PullRequestNotification).filter(
                    and_(
                        PullRequestNotification.id == notification_id,
                        PullRequestNotification.user_id == user_id
                    )
                ).first()
                
                if notification:
                    notification.slack_sent = True
                    updated_count += 1
                else:
                    failed_ids.append(notification_id)
            
            db.commit()
            
            result = {
                "success": True,
                "updated_count": updated_count,
                "failed_count": len(failed_ids),
                "failed_ids": failed_ids
            }
            
            logger.info(f"Bulk marked {updated_count} notifications as Slack sent for user {user_id}")
            return result
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error in bulk mark Slack sent: {str(e)}")
            return {
                "success": False,
                "updated_count": 0,
                "failed_count": len(notification_ids),
                "error": str(e)
            }

    @staticmethod
    def search_pr_notifications(
        db: Session,
        user_id: str,
        search_query: str,
        search_fields: List[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        exact_match: bool = False
    ) -> List[PRNotificationSummary]:
        """Advanced search functionality for PR notifications"""
        try:
            if not search_fields:
                search_fields = ["pr_title", "repo_name", "subject"]
            
            # Base query
            query = db.query(PullRequestNotification).filter(
                PullRequestNotification.user_id == user_id
            )
            
            # Date range filter
            if date_from:
                query = query.filter(PullRequestNotification.received_at >= date_from)
            if date_to:
                query = query.filter(PullRequestNotification.received_at <= date_to)
            
            # Search conditions
            search_conditions = []
            for field in search_fields:
                if hasattr(PullRequestNotification, field):
                    column = getattr(PullRequestNotification, field)
                    if exact_match:
                        condition = column == search_query
                    else:
                        condition = column.ilike(f"%{search_query}%")
                    search_conditions.append(condition)
            
            if search_conditions:
                query = query.filter(or_(*search_conditions))
            
            # Execute query
            notifications = query.order_by(
                desc(PullRequestNotification.received_at)
            ).limit(100).all()  # Limit search results
            
            # Convert to summary format
            results = [
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
            
            logger.info(f"Search returned {len(results)} results for query: {search_query}")
            return results
            
        except Exception as e:
            logger.error(f"Error in search: {str(e)}")
            return []

    @staticmethod
    def get_repository_stats(db: Session, user_id: str, repo_name: str) -> Dict[str, Any]:
        """Get detailed statistics for a specific repository"""
        try:
            # Base query for the repository
            repo_query = db.query(PullRequestNotification).filter(
                and_(
                    PullRequestNotification.user_id == user_id,
                    PullRequestNotification.repo_name == repo_name
                )
            )
            
            total_prs = repo_query.count()
            
            # Status breakdown
            open_prs = repo_query.filter(PullRequestNotification.pr_status == 'opened').count()
            merged_prs = repo_query.filter(PullRequestNotification.pr_status == 'merged').count()
            closed_prs = repo_query.filter(PullRequestNotification.pr_status == 'closed').count()
            
            # Last activity
            last_notification = repo_query.order_by(
                desc(PullRequestNotification.received_at)
            ).first()
            
            # Activity over time (last 30 days)
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            recent_activity = {}
            
            for i in range(30):
                date = thirty_days_ago + timedelta(days=i)
                date_str = date.strftime('%Y-%m-%d')
                
                count = repo_query.filter(
                    func.date(PullRequestNotification.received_at) == date.date()
                ).count()
                recent_activity[date_str] = count
            
            return {
                "repo_name": repo_name,
                "total_prs": total_prs,
                "open_prs": open_prs,
                "merged_prs": merged_prs,
                "closed_prs": closed_prs,
                "last_activity": last_notification.received_at if last_notification else None,
                "recent_activity": recent_activity,
                "activity_trend": sum(recent_activity.values())
            }
            
        except Exception as e:
            logger.error(f"Error getting repository stats for {repo_name}: {str(e)}")
            return {}