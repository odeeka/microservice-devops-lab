import os
import logging
from logging.handlers import QueueHandler, QueueListener
from pathlib import Path
from contextlib import asynccontextmanager
import queue

import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
import time

from config import get_settings
from db.database import DatabaseManager
from api.routes import router as api_router
from api.auth_routes import router as auth_router
from api.user_routes import router as user_router
from api.session_routes import router as session_router
from api.admin_routes import router as admin_router
from services.cache_service import get_cache
from middleware.rate_limit import RateLimitMiddleware
from middleware.auto_token_refresh import AutoTokenRefreshMiddleware
from middleware.session_activity import SessionActivityMiddleware

# Create logs directory if it doesn't exist
logs_dir = Path("/app/logs")
logs_dir.mkdir(exist_ok=True, parents=True)

# Setup async-friendly logging with queue handler (non-blocking)
log_queue = queue.Queue(-1)
queue_handler = QueueHandler(log_queue)

file_handler = logging.FileHandler(logs_dir / 'app.log') if logs_dir.exists() else logging.NullHandler()
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

queue_listener = QueueListener(log_queue, file_handler, logging.StreamHandler())
queue_listener.start()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[queue_handler]
)

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    settings = get_settings()
    logger.info("🚀 Starting up application...")
    
    # Initialize database connection pool
    db_manager = DatabaseManager()
    try:
        await db_manager.init_db()
        logger.info("✅ Database initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {e}")
        raise
    
    # Initialize users table
    try:
        logger.info("📋 Initializing users table...")
        init_users_sql_path = Path("/app/db/init_users.sql")
        if init_users_sql_path.exists():
            with open(init_users_sql_path, 'r') as f:
                init_sql = f.read()
            await db_manager.execute(init_sql)
            logger.info("✅ Users table initialized")
        else:
            logger.warning("⚠️  init_users.sql not found, skipping users table creation")
    except Exception as e:
        logger.error(f"❌ Failed to initialize users table: {e}")
        # Don't fail startup
    
    # Initialize sessions table
    try:
        logger.info("📋 Initializing sessions table...")
        init_sessions_sql_path = Path("/app/db/init_sessions.sql")
        if init_sessions_sql_path.exists():
            with open(init_sessions_sql_path, 'r') as f:
                init_sql = f.read()
            await db_manager.execute(init_sql)
            logger.info("✅ Sessions table initialized")
        else:
            logger.warning("⚠️  init_sessions.sql not found, skipping sessions table creation")
    except Exception as e:
        logger.error(f"❌ Failed to initialize sessions table: {e}")
        # Don't fail startup
    
    # Generate default users and fake users if enabled
    if settings.enable_fake_data:
        try:
            logger.info("👥 Generating default users...")
            from services.user_generator import UserGenerator
            
            user_generator = UserGenerator()
            
            # Create default users (admin, testuser, readonly)
            default_users = await user_generator.create_default_users()
            if default_users:
                logger.info(f"✅ Created {len(default_users)} default users")
                logger.info("   - admin@example.com / Admin123!")
                logger.info("   - user@example.com / User123!")
                logger.info("   - readonly@example.com / Readonly123!")
            
            # Generate additional fake users
            fake_user_count = await user_generator.populate_users(count=20)
            if fake_user_count > 0:
                logger.info(f"✅ Generated {fake_user_count} additional fake users")
            
        except Exception as e:
            logger.error(f"⚠️  Failed to generate users: {e}")
            # Don't fail startup
    
    # Generate fake data if enabled
    if settings.enable_fake_data:
        try:
            logger.info("🎲 Fake data generation is enabled")
            from services.data_generator import DataGenerator
            
            generator = DataGenerator()
            
            # Log configuration
            config = await generator.get_generation_config()
            logger.info(f"📋 Fake data config: {config}")
            
            # Generate data
            created_count = await generator.populate_database()
            
            if created_count > 0:
                logger.info(f"✅ Generated {created_count} fake items")
            else:
                logger.info("ℹ️  No fake data generated (database not empty or disabled)")
                
        except Exception as e:
            logger.error(f"⚠️  Failed to generate fake data: {e}")
            # Don't fail startup if fake data generation fails
    else:
        logger.info("ℹ️  Fake data generation is disabled")
    
    # Test Redis connection
    cache_service = get_cache()
    redis_available = await cache_service.ping()
    if redis_available:
        logger.info("✅ Redis connection established")
    else:
        logger.warning("⚠️  Redis is not available - caching disabled")
    
    yield
    
    logger.info("🛑 Shutting down application...")
    await db_manager.close_all_connections()
    await cache_service.close()
    queue_listener.stop()

def create_app() -> FastAPI:
    settings = get_settings()
    
    app = FastAPI(
        title="Microservice DevOps Lab API",
        description="A production-ready FastAPI microservice with monitoring and observability",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_hosts,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        allow_headers=["*"],
    )

    # Add trusted host middleware
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.allowed_hosts
    )

    # Add rate limiting middleware (IP-based with Redis)
    if settings.rate_limit_enabled:
        app.add_middleware(
            RateLimitMiddleware,
            requests_per_minute=settings.rate_limit_requests_per_minute,
            block_duration=settings.rate_limit_block_duration
        )
        logger.info(
            f"✅ Rate limiting enabled: {settings.rate_limit_requests_per_minute} "
            f"requests/minute per IP, block for {settings.rate_limit_block_duration}s"
        )
    else:
        logger.info("⚠️  Rate limiting disabled via configuration")
    
    # Add auto token refresh middleware (Phase 3 feature)
    app.add_middleware(AutoTokenRefreshMiddleware)
    logger.info("✅ Auto token refresh middleware enabled")
    
    # Add session activity tracking middleware (Phase 3 feature)
    app.add_middleware(SessionActivityMiddleware)
    logger.info("✅ Session activity tracking middleware enabled")

    # Add request timing middleware (async)
    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        logger.info(f"Request {request.method} {request.url.path} processed in {process_time:.4f}s")
        return response

    # Add exception handler (async)
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Global exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"}
        )

    # Health check endpoints (async)
    @app.get("/health", tags=["Health"])
    async def health_check():
        """Basic health check"""
        return {"status": "healthy", "service": "microservice-devops-lab"}

    @app.get("/health/detailed", tags=["Health"])
    async def detailed_health_check():
        """Detailed health check with database connectivity"""
        db_manager = DatabaseManager()
        db_status = "healthy"
        try:
            async with db_manager.get_connection() as conn:
                await conn.fetchval("SELECT 1")
        except Exception as e:
            db_status = f"unhealthy: {str(e)}"
            logger.error(f"Database health check failed: {e}")
        
        return {
            "status": "healthy" if db_status == "healthy" else "unhealthy",
            "service": "microservice-devops-lab",
            "database": db_status,
            "version": "1.0.0"
        }

    # Include API routers
    app.include_router(api_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(user_router, prefix="/api/v1")
    app.include_router(session_router, prefix="/api/v1")
    app.include_router(admin_router, prefix="/api/v1")

    # Initialize Prometheus instrumentation if enabled
    if settings.enable_metrics:
        instrumentator = Instrumentator()
        instrumentator.instrument(app)
        instrumentator.expose(app, endpoint="/metrics")
        logger.info("📊 Prometheus metrics enabled at /metrics")

    logger.info("✅ Application created successfully")
    return app

app = create_app()

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
