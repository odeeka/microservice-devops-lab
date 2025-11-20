"""
Session Activity Tracking Middleware

Tracks user activity by updating session last_active timestamp on every request.
Uses Redis cache to prevent database spam and improve performance.
"""
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from datetime import datetime
import logging
import hashlib

from core.auth import decode_token
from services.cache_service import get_cache
from db.database import get_db_session

logger = logging.getLogger(__name__)

# How often to update last_active in database (seconds)
ACTIVITY_UPDATE_INTERVAL = 60  # Update DB at most once per minute


class SessionActivityMiddleware(BaseHTTPMiddleware):
    """
    Middleware to track user session activity.
    
    How it works:
    1. Extracts JWT token from Authorization header
    2. Checks Redis cache for recent activity update
    3. If not updated recently, updates session last_active in database
    4. Caches update time in Redis to prevent DB spam
    
    Benefits:
    - Real-time session activity tracking
    - Efficient (uses cache to minimize DB writes)
    - Enables auto-logout for inactive sessions
    - Provides accurate "last seen" timestamps
    
    Performance:
    - DB writes: Max 1 per minute per session
    - Redis reads: Every request (fast)
    - Redis writes: Max 1 per minute per session
    """
    
    async def dispatch(self, request: Request, call_next):
        """
        Process request and track session activity.
        """
        # Extract Authorization header
        auth_header = request.headers.get("Authorization")
        
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split("Bearer ")[1]
            
            try:
                # Decode token to get user info
                payload = decode_token(token)
                
                # Only track access tokens (not refresh tokens)
                if payload.get("type") != "refresh":
                    user_id = payload.get("sub")
                    
                    if user_id:
                        # Generate cache key for this session
                        # Use token hash to uniquely identify session
                        token_hash = hashlib.sha256(token.encode()).hexdigest()[:16]
                        cache_key = f"session_activity:{user_id}:{token_hash}"
                        
                        # Check if we recently updated this session
                        cache_service = get_cache()
                        last_update = await cache_service.get(cache_key)
                        
                        if not last_update:
                            # Haven't updated recently - update database
                            await self._update_session_activity(token, token_hash)
                            
                            # Cache the update time to prevent DB spam
                            await cache_service.set(
                                cache_key,
                                datetime.utcnow().isoformat(),
                                expire=ACTIVITY_UPDATE_INTERVAL
                            )
                            
                            logger.debug(
                                f"📊 Updated session activity for user_id={user_id}"
                            )
            
            except Exception as e:
                # Don't fail requests if activity tracking fails
                logger.debug(f"Session activity tracking error: {e}")
        
        # Process request
        response = await call_next(request)
        return response
    
    async def _update_session_activity(self, token: str, token_hash: str):
        """
        Update session last_active timestamp in database.
        
        Args:
            token: JWT access token
            token_hash: Short hash of token for identification
        """
        try:
            # Get database session
            async for db_session in get_db_session():
                query = """
                    UPDATE user_sessions
                    SET last_active = $1
                    WHERE session_token = $2
                        AND is_revoked = FALSE
                        AND expires_at > $1
                """
                
                now = datetime.utcnow()
                
                # Hash the full token for lookup (stored as SHA256)
                full_token_hash = hashlib.sha256(token.encode()).hexdigest()
                
                result = await db_session.execute(
                    query,
                    now,
                    full_token_hash
                )
                
                # Check if session was updated
                rows_affected = result.split()[-1] if result else "0"
                
                if rows_affected != "0":
                    logger.debug(f"✅ Session last_active updated: {token_hash}")
                
                break  # Only need one iteration
        
        except Exception as e:
            logger.warning(f"Failed to update session activity: {e}")
