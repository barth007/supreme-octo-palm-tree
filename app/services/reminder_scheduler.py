# =============================================================================
# app/services/reminder_scheduler.py (CORRECTED)
# =============================================================================
"""
Automated scheduler for PR reminders using APScheduler
This runs periodic tasks independently of API requests
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.services.background_tasks_service import PRReminderBackgroundService
from app.core.config import settings
from app.core.logger import get_module_logger

logger = get_module_logger(__name__, "logs/reminder_scheduler.log")

class ReminderScheduler:
    """Automated scheduler for PR reminders and maintenance tasks"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.is_running = False
    
    def start(self):
        """Start the scheduler with all configured jobs"""
        if self.is_running:
            logger.warning("Scheduler is already running")
            return
        
        try:
            # Schedule daily PR reminders (weekdays at 9 AM)
            self.scheduler.add_job(
                func=self._daily_pr_reminders,
                trigger=CronTrigger(
                    day_of_week='mon-fri',  # Monday to Friday
                    hour=9,                 # 9 AM
                    minute=0,
                    timezone='UTC'
                ),
                id='daily_pr_reminders',
                name='Daily PR Reminders',
                replace_existing=True
            )
            
            # Schedule daily summaries (weekdays at 8 AM)
            self.scheduler.add_job(
                func=self._daily_summaries,
                trigger=CronTrigger(
                    day_of_week='mon-fri',  # Monday to Friday
                    hour=8,                 # 8 AM
                    minute=0,
                    timezone='UTC'
                ),
                id='daily_summaries',
                name='Daily PR Summaries',
                replace_existing=True
            )
            
            # Schedule weekly cleanup (Sundays at 2 AM)
            self.scheduler.add_job(
                func=self._weekly_cleanup,
                trigger=CronTrigger(
                    day_of_week='sun',      # Sunday
                    hour=2,                 # 2 AM
                    minute=0,
                    timezone='UTC'
                ),
                id='weekly_cleanup',
                name='Weekly Cleanup',
                replace_existing=True
            )
            
            # Schedule urgent reminders (daily at 2 PM for PRs > 7 days old)
            self.scheduler.add_job(
                func=self._urgent_pr_reminders,
                trigger=CronTrigger(
                    day_of_week='mon-fri',  # Monday to Friday
                    hour=14,                # 2 PM
                    minute=0,
                    timezone='UTC'
                ),
                id='urgent_pr_reminders',
                name='Urgent PR Reminders',
                replace_existing=True
            )
            
            # Start the scheduler
            self.scheduler.start()
            self.is_running = True
            
            logger.info("Reminder scheduler started successfully")
            logger.info("Scheduled jobs:")
            for job in self.scheduler.get_jobs():
                logger.info(f"  - {job.name} (ID: {job.id}) - Next run: {job.next_run_time}")
            
        except Exception as e:
            logger.error(f"Failed to start reminder scheduler: {str(e)}")
            raise
    
    def stop(self):
        """Stop the scheduler"""
        if not self.is_running:
            logger.warning("Scheduler is not running")
            return
        
        try:
            self.scheduler.shutdown(wait=False)
            self.is_running = False
            logger.info("Reminder scheduler stopped")
        except Exception as e:
            logger.error(f"Error stopping scheduler: {str(e)}")
    
    def add_custom_reminder_job(
        self,
        user_id: str,
        schedule_time: datetime,
        threshold_days: int = 2
    ):
        """Add a custom one-time reminder job for a specific user"""
        try:
            job_id = f"custom_reminder_{user_id}_{int(schedule_time.timestamp())}"
            
            self.scheduler.add_job(
                func=self._custom_user_reminder,
                trigger='date',
                run_date=schedule_time,
                args=[user_id, threshold_days],
                id=job_id,
                name=f'Custom Reminder for User {user_id}',
                replace_existing=True
            )
            
            logger.info(f"Custom reminder job scheduled for user {user_id} at {schedule_time}")
            return job_id
            
        except Exception as e:
            logger.error(f"Failed to schedule custom reminder: {str(e)}")
            raise
    
    def remove_job(self, job_id: str) -> bool:
        """Remove a scheduled job"""
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"Removed job: {job_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to remove job {job_id}: {str(e)}")
            return False
    
    def get_scheduled_jobs(self):
        """Get list of all scheduled jobs"""
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                'id': job.id,
                'name': job.name,
                'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                'trigger': str(job.trigger)
            })
        return jobs
    
    # =============================================================================
    # Scheduled Task Functions
    # =============================================================================
    
    async def _daily_pr_reminders(self):
        """Daily PR reminder task (9 AM weekdays)"""
        logger.info("Starting daily PR reminders task")
        
        db = SessionLocal()
        try:
            result = PRReminderBackgroundService.send_pr_reminders_task(
                db=db,
                reminder_threshold_days=2,  # Remind about PRs older than 2 days
                max_reminders_per_user=10
            )
            
            logger.info(f"Daily reminders completed: {result}")
            
        except Exception as e:
            logger.error(f"Error in daily PR reminders task: {str(e)}")
        finally:
            db.close()
    
    async def _urgent_pr_reminders(self):
        """Urgent PR reminder task (2 PM weekdays for old PRs)"""
        logger.info("Starting urgent PR reminders task")
        
        db = SessionLocal()
        try:
            result = PRReminderBackgroundService.send_pr_reminders_task(
                db=db,
                reminder_threshold_days=7,  # Remind about PRs older than 7 days (urgent)
                max_reminders_per_user=5   # Fewer reminders for urgent cases
            )
            
            logger.info(f"Urgent reminders completed: {result}")
            
        except Exception as e:
            logger.error(f"Error in urgent PR reminders task: {str(e)}")
        finally:
            db.close()
    
    async def _daily_summaries(self):
        """Daily summary task (8 AM weekdays)"""
        logger.info("Starting daily summaries task")
        
        db = SessionLocal()
        try:
            result = PRReminderBackgroundService.send_daily_summaries_task(db=db)
            logger.info(f"Daily summaries completed: {result}")
            
        except Exception as e:
            logger.error(f"Error in daily summaries task: {str(e)}")
        finally:
            db.close()
    
    async def _weekly_cleanup(self):
        """Weekly cleanup task (Sunday 2 AM)"""
        logger.info("Starting weekly cleanup task")
        
        db = SessionLocal()
        try:
            result = PRReminderBackgroundService.cleanup_old_notifications_task(
                db=db,
                cleanup_threshold_days=90  # Clean up notifications older than 90 days
            )
            
            logger.info(f"Weekly cleanup completed: {result}")
            
        except Exception as e:
            logger.error(f"Error in weekly cleanup task: {str(e)}")
        finally:
            db.close()
    
    async def _custom_user_reminder(self, user_id: str, threshold_days: int):
        """Custom reminder for a specific user"""
        logger.info(f"Starting custom reminder for user {user_id}")
        
        db = SessionLocal()
        try:
            from app.models.user import User
            
            # Get the user
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                logger.error(f"User {user_id} not found for custom reminder")
                return
            
            # Get old PRs for this user
            old_prs = PRReminderBackgroundService._get_old_open_prs(
                db, user_id, threshold_days
            )
            
            if old_prs:
                # Send reminders
                result = PRReminderBackgroundService._send_user_pr_reminders(
                    db, user, old_prs
                )
                
                if result.get("success"):
                    # Mark as sent
                    PRReminderBackgroundService._mark_prs_slack_sent(db, old_prs)
                    logger.info(f"Custom reminder sent to {user.email}: {len(old_prs)} PRs")
                else:
                    logger.error(f"Failed to send custom reminder to {user.email}")
            else:
                logger.info(f"No old PRs found for custom reminder to {user.email}")
                
        except Exception as e:
            logger.error(f"Error in custom user reminder for {user_id}: {str(e)}")
        finally:
            db.close()


# =============================================================================
# Global Scheduler Instance
# =============================================================================

# Global scheduler instance
reminder_scheduler = ReminderScheduler()

def start_reminder_scheduler():
    """Start the global reminder scheduler"""
    try:
        reminder_scheduler.start()
        logger.info("Global reminder scheduler started")
    except Exception as e:
        logger.error(f"Failed to start global reminder scheduler: {str(e)}")

def stop_reminder_scheduler():
    """Stop the global reminder scheduler"""
    try:
        reminder_scheduler.stop()
        logger.info("Global reminder scheduler stopped")
    except Exception as e:
        logger.error(f"Failed to stop global reminder scheduler: {str(e)}")

def get_scheduler_status():
    """Get status of the global scheduler"""
    return {
        "running": reminder_scheduler.is_running,
        "jobs": reminder_scheduler.get_scheduled_jobs() if reminder_scheduler.is_running else []
    }


# =============================================================================
# FastAPI Lifespan Integration
# =============================================================================

async def startup_scheduler():
    """Start scheduler on FastAPI startup"""
    logger.info("Starting reminder scheduler on FastAPI startup")
    start_reminder_scheduler()

async def shutdown_scheduler():
    """Stop scheduler on FastAPI shutdown"""
    logger.info("Stopping reminder scheduler on FastAPI shutdown")
    stop_reminder_scheduler()


# =============================================================================
# Configuration-based Scheduler Setup
# =============================================================================

class SchedulerConfig:
    """Configuration for reminder scheduler"""
    
    # Default schedule times (can be overridden via environment variables)
    DAILY_REMINDER_HOUR = 9      # 9 AM
    DAILY_SUMMARY_HOUR = 8       # 8 AM  
    URGENT_REMINDER_HOUR = 14    # 2 PM
    WEEKLY_CLEANUP_DAY = 'sun'   # Sunday
    WEEKLY_CLEANUP_HOUR = 2      # 2 AM
    
    # Reminder thresholds
    DAILY_REMINDER_THRESHOLD = 2    # Remind about PRs older than 2 days
    URGENT_REMINDER_THRESHOLD = 7   # Urgent reminders for PRs older than 7 days
    CLEANUP_THRESHOLD = 90          # Clean up notifications older than 90 days
    
    # Limits
    MAX_REMINDERS_PER_USER = 10
    MAX_URGENT_REMINDERS_PER_USER = 5

def create_custom_scheduler(config: SchedulerConfig = None):
    """Create a scheduler with custom configuration"""
    if config is None:
        config = SchedulerConfig()
    
    scheduler = ReminderScheduler()
    
    # Override default schedules with custom config
    # This would replace the hardcoded schedules in the start() method
    # Implementation would depend on specific requirements
    
    return scheduler


# =============================================================================
# Manual Trigger Functions for Testing
# =============================================================================

async def trigger_manual_daily_reminders():
    """Manually trigger daily reminders (for testing)"""
    logger.info("Manually triggering daily reminders")
    await reminder_scheduler._daily_pr_reminders()

async def trigger_manual_daily_summaries():
    """Manually trigger daily summaries (for testing)"""
    logger.info("Manually triggering daily summaries")
    await reminder_scheduler._daily_summaries()

async def trigger_manual_cleanup():
    """Manually trigger cleanup (for testing)"""
    logger.info("Manually triggering cleanup")
    await reminder_scheduler._weekly_cleanup()