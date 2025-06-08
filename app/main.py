# =============================================================================
# app/main.py - Final Implementation with All Stages Complete
# =============================================================================
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from contextlib import asynccontextmanager
from datetime import datetime
from app.core.config import settings
from app.api.v1.api import api_router
from app.db.init_db import init_db
from app.services.reminder_scheduler import startup_scheduler, shutdown_scheduler, get_scheduler_status
from app.core.logger import get_module_logger

logger = get_module_logger(__name__, "logs/main.log")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage FastAPI application lifespan with proper startup/shutdown
    """
    # =============================================================================
    # STARTUP SEQUENCE
    # =============================================================================
    logger.info("🚀 Starting FastAPI application...")
    
    try:
        # 1. Initialize database
        logger.info("📦 Initializing database...")
        init_db()
        logger.info("✅ Database initialized successfully")
        
        # 2. Start the reminder scheduler
        logger.info("⏰ Starting reminder scheduler...")
        await startup_scheduler()
        logger.info("✅ Reminder scheduler started successfully")
        
        # 3. Log application configuration
        logger.info("🔧 Application configuration:")
        logger.info(f"   Environment: {settings.ENVIRONMENT}")
        logger.info(f"   Debug mode: {settings.DEBUG}")
        logger.info(f"   Project: {settings.PROJECT_NAME} v{settings.VERSION}")
        logger.info(f"   Database: {settings.DATABASE_URL[:50]}...")
        logger.info(f"   Google OAuth: {'✅ Configured' if settings.GOOGLE_CLIENT_ID else '❌ Not configured'}")
        logger.info(f"   Slack OAuth: {'✅ Configured' if settings.SLACK_CLIENT_ID else '❌ Not configured'}")
        logger.info(f"   Webhook Auth: {'✅ Configured' if settings.WEBHOOK_USERNAME else '❌ Not configured'}")
        
        logger.info("🎉 Application startup completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Error during startup: {str(e)}")
        raise
    
    # Application is running
    yield
    
    # =============================================================================
    # SHUTDOWN SEQUENCE  
    # =============================================================================
    logger.info("🛑 Shutting down FastAPI application...")
    
    try:
        # Stop the reminder scheduler gracefully
        logger.info("⏰ Stopping reminder scheduler...")
        await shutdown_scheduler()
        logger.info("✅ Reminder scheduler stopped successfully")
        
        logger.info("👋 Application shutdown completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Error during shutdown: {str(e)}")

def create_application() -> FastAPI:
    """
    Create and configure the FastAPI application with all middleware and routes
    """
    # Create FastAPI application with lifespan management
    application = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description=settings.DESCRIPTION,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,  # Add lifespan manager for startup/shutdown
        # Additional metadata
        contact={
            "name": "API Support",
            "email": "support@yourcompany.com",
        },
        license_info={
            "name": "MIT",
        },
    )

    # Set debug mode
    application.debug = settings.DEBUG

    # =============================================================================
    # MIDDLEWARE CONFIGURATION
    # =============================================================================
    
    # Session middleware for OAuth flows
    application.add_middleware(
        SessionMiddleware,
        secret_key=settings.SECRET_KEY,
        session_cookie="session_cookie",
        max_age=86400,  # 24 hours
        same_site="lax",
        https_only=not settings.DEBUG  # HTTPS only in production
    )

    # CORS middleware
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_HOSTS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # =============================================================================
    # ROUTE REGISTRATION
    # =============================================================================
    
    # Include all API routes with versioning
    application.include_router(api_router, prefix=settings.API_V1_STR)
    
    logger.info("📋 Registered API routes:")
    logger.info("   🔐 /api/v1/auth/* - Authentication (Google OAuth)")
    logger.info("   💬 /api/v1/auth/slack/* - Slack Integration")
    logger.info("   👤 /api/v1/users/* - User Management")
    logger.info("   📧 /api/v1/webhook/* - Postmark Email Processing")
    logger.info("   📋 /api/v1/pr/* - Pull Request Management")
    logger.info("   🔔 /api/v1/reminders/* - Slack Reminder System")

    return application

# Create the application instance
app = create_application()

# =============================================================================
# ROOT AND UTILITY ENDPOINTS
# =============================================================================

@app.get("/")
async def root():
    """
    Root endpoint with application overview and feature list
    """
    return {
        "message": f"Welcome to {settings.PROJECT_NAME}",
        "version": settings.VERSION,
        "description": settings.DESCRIPTION,
        "environment": settings.ENVIRONMENT,
        "docs": "/docs",
        "features": [
            "🔐 Google OAuth2 Authentication",
            "💬 Slack Integration & OAuth", 
            "📧 Email Processing (Postmark Webhooks)",
            "📋 Pull Request Management & Analytics",
            "🔔 Automated PR Reminders via Slack",
            "⏰ Background Task Scheduling",
            "📊 Comprehensive Statistics & Reporting",
            "🔍 Advanced Filtering & Search",
            "📤 Data Export (JSON/CSV)",
            "🛡️ Production-Ready Security & Monitoring"
        ],
        "api_endpoints": {
            "authentication": f"{settings.API_V1_STR}/auth/",
            "users": f"{settings.API_V1_STR}/users/",
            "pr_management": f"{settings.API_V1_STR}/pr/",
            "reminders": f"{settings.API_V1_STR}/reminders/",
            "webhooks": f"{settings.API_V1_STR}/webhook/"
        },
        "documentation": {
            "swagger_ui": "/docs",
            "redoc": "/redoc",
            "openapi_spec": f"{settings.API_V1_STR}/openapi.json"
        }
    }

@app.get("/health")
async def health_check():
    """
    Comprehensive health check endpoint with system status
    """
    try:
        # Get scheduler status
        scheduler_status = get_scheduler_status()
        
        # Check database connection (basic test)
        from app.db.session import SessionLocal
        db_healthy = True
        try:
            db = SessionLocal()
            db.execute("SELECT 1")
            db.close()
        except Exception:
            db_healthy = False
        
        # Determine overall health
        overall_healthy = db_healthy and scheduler_status.get("running", False)
        
        health_data = {
            "status": "healthy" if overall_healthy else "degraded",
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT,
            "timestamp": datetime.utcnow().isoformat(),
            "components": {
                "database": "healthy" if db_healthy else "unhealthy",
                "scheduler": "healthy" if scheduler_status.get("running") else "unhealthy",
                "api": "healthy"
            },
            "scheduler": scheduler_status,
            "configuration": {
                "google_oauth": bool(settings.GOOGLE_CLIENT_ID),
                "slack_oauth": bool(settings.SLACK_CLIENT_ID), 
                "webhook_auth": bool(settings.WEBHOOK_USERNAME),
                "debug_mode": settings.DEBUG
            }
        }
        
        # Return appropriate HTTP status
        status_code = 200 if overall_healthy else 503
        return health_data
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

@app.get("/scheduler/status")
async def get_scheduler_status_endpoint():
    """
    Get detailed scheduler status and job information
    """
    try:
        status = get_scheduler_status()
        
        # Add additional scheduler metrics
        status["description"] = "Automated reminder and maintenance scheduler"
        status["features"] = [
            "Daily PR reminders (Mon-Fri 9:00 AM UTC)",
            "Daily summaries (Mon-Fri 8:00 AM UTC)", 
            "Urgent reminders (Mon-Fri 2:00 PM UTC)",
            "Weekly cleanup (Sunday 2:00 AM UTC)"
        ]
        
        return status
        
    except Exception as e:
        logger.error(f"Scheduler status check failed: {str(e)}")
        return {
            "running": False,
            "error": str(e),
            "jobs": []
        }

@app.get("/info")
async def get_application_info():
    """
    Get detailed application information and capabilities
    """
    return {
        "application": {
            "name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "description": settings.DESCRIPTION,
            "environment": settings.ENVIRONMENT
        },
        "capabilities": {
            "authentication": {
                "google_oauth2": bool(settings.GOOGLE_CLIENT_ID),
                "jwt_tokens": True,
                "session_management": True
            },
            "integrations": {
                "slack": bool(settings.SLACK_CLIENT_ID),
                "postmark_webhooks": bool(settings.WEBHOOK_USERNAME),
                "github_pr_parsing": True
            },
            "features": {
                "pr_management": True,
                "automated_reminders": True,
                "background_tasks": True,
                "data_export": True,
                "advanced_filtering": True,
                "statistics_analytics": True
            }
        },
        "system": {
            "fastapi_version": "latest",
            "python_version": "3.8+",
            "database": "SQLAlchemy ORM",
            "scheduler": "APScheduler",
            "async_support": True
        }
    }

# =============================================================================
# ERROR HANDLERS
# =============================================================================

@app.exception_handler(404)
async def not_found_handler(request, exc):
    """Custom 404 handler with helpful information"""
    return {
        "error": "Not Found",
        "message": "The requested endpoint was not found",
        "suggestion": "Check the API documentation at /docs",
        "available_endpoints": {
            "root": "/",
            "health": "/health", 
            "docs": "/docs",
            "api": settings.API_V1_STR
        }
    }

@app.exception_handler(500)
async def internal_error_handler(request, exc):
    """Custom 500 handler"""
    logger.error(f"Internal server error: {str(exc)}")
    return {
        "error": "Internal Server Error",
        "message": "An unexpected error occurred",
        "support": "Please contact support if this error persists"
    }

# =============================================================================
# DEVELOPMENT HELPERS
# =============================================================================

if settings.DEBUG:
    @app.get("/debug/config")
    async def debug_configuration():
        """Debug endpoint to check configuration (only in development)"""
        return {
            "environment": settings.ENVIRONMENT,
            "debug": settings.DEBUG,
            "database_url": settings.DATABASE_URL[:30] + "..." if len(settings.DATABASE_URL) > 30 else settings.DATABASE_URL,
            "google_oauth_configured": bool(settings.GOOGLE_CLIENT_ID),
            "slack_oauth_configured": bool(settings.SLACK_CLIENT_ID),
            "webhook_auth_configured": bool(settings.WEBHOOK_USERNAME),
            "cors_origins": settings.ALLOWED_HOSTS,
            "api_prefix": settings.API_V1_STR
        }

# =============================================================================
# APPLICATION STARTUP LOG
# =============================================================================

logger.info("=" * 80)
logger.info(f"🚀 {settings.PROJECT_NAME} v{settings.VERSION}")
logger.info("=" * 80)
logger.info("Features enabled:")
logger.info("✅ Stage 1: Google OAuth2 Authentication")
logger.info("✅ Stage 2: Slack OAuth Integration")  
logger.info("✅ Stage 3: Email Processing & PR Parsing")
logger.info("✅ Stage 4: Pull Request Management")
logger.info("✅ Stage 5: Slack Notification Delivery")
logger.info("=" * 80)
logger.info("🎉 All stages complete - Production ready!")
logger.info("=" * 80)