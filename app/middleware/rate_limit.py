"""Redis-based rate limiting middleware for FastAPI"""
import time
from typing import Optional, Tuple
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    IP-based rate limiting using Redis.
    
    Blocks requests exceeding the configured limit per time window.
    """
    
    def __init__(self, app, requests_per_minute: int = 60, block_duration: int = 60):
        """
        Initialize rate limiter.
        
        Args:
            app: FastAPI application
            requests_per_minute: Maximum requests allowed per IP per minute (default: 60)
            block_duration: How long to block IP after exceeding limit in seconds (default: 60)
        """
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.block_duration = block_duration
        self._cache_service = None
        
        # Excluded paths from rate limiting
        self.excluded_paths = {
            "/health",
            "/metrics",
            "/docs",
            "/redoc",
            "/openapi.json"
        }
    
    @property
    def cache_service(self):
        """Lazy load cache service"""
        if self._cache_service is None:
            from services.cache_service import get_cache
            self._cache_service = get_cache()
        return self._cache_service
    
    async def dispatch(self, request: Request, call_next):
        """Process each request and apply rate limiting"""
        
        # Skip rate limiting for excluded paths
        if request.url.path in self.excluded_paths:
            return await call_next(request)
        
        # Skip if Redis is not available
        if not self.cache_service or not self.cache_service.redis_client:
            logger.debug("Rate limiting disabled - Redis not available")
            return await call_next(request)
        
        # Get client IP
        client_ip = self._get_client_ip(request)
        
        try:
            # Check if IP is currently blocked
            is_blocked, block_expires_in = await self._is_ip_blocked(client_ip)
            if is_blocked:
                logger.warning(
                    f"⛔ Rate limit BLOCKED: {client_ip} - "
                    f"Blocked for {block_expires_in}s more"
                )
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "error": "Rate limit exceeded",
                        "message": f"Too many requests. Try again in {block_expires_in} seconds.",
                        "retry_after": block_expires_in
                    },
                    headers={"Retry-After": str(block_expires_in)}
                )
            
            # Check and increment request count
            current_count, should_block = await self._check_and_increment(client_ip)
            
            if should_block:
                # Block the IP
                await self._block_ip(client_ip)
                logger.warning(
                    f"⛔ Rate limit EXCEEDED: {client_ip} - "
                    f"{current_count} requests in 60s - BLOCKING for {self.block_duration}s"
                )
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "error": "Rate limit exceeded",
                        "message": f"You made {current_count} requests in 1 minute. Limit is {self.requests_per_minute}. Blocked for {self.block_duration} seconds.",
                        "retry_after": self.block_duration
                    },
                    headers={"Retry-After": str(self.block_duration)}
                )
            
            # Log rate limit info (only every 10 requests to avoid log spam)
            if current_count % 10 == 0 or current_count > self.requests_per_minute * 0.8:
                remaining = self.requests_per_minute - current_count
                logger.info(
                    f"🚦 Rate limit: {client_ip} - "
                    f"{current_count}/{self.requests_per_minute} requests - "
                    f"{remaining} remaining"
                )
            
            # Add rate limit headers to response
            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
            response.headers["X-RateLimit-Remaining"] = str(max(0, self.requests_per_minute - current_count))
            response.headers["X-RateLimit-Reset"] = str(60)  # 60 seconds window
            
            return response
            
        except Exception as e:
            logger.error(f"Error in rate limiting for {client_ip}: {e}", exc_info=True)
            # On error, allow request to proceed
            return await call_next(request)
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request (handles proxies)"""
        # Check X-Forwarded-For header first (for proxied requests)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Take the first IP in the chain
            return forwarded.split(",")[0].strip()
        
        # Check X-Real-IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fallback to direct client
        return request.client.host if request.client else "unknown"
    
    async def _is_ip_blocked(self, ip: str) -> Tuple[bool, int]:
        """
        Check if IP is currently blocked.
        
        Returns:
            Tuple of (is_blocked: bool, seconds_remaining: int)
        """
        if not self.cache_service.redis_client:
            return False, 0  # No Redis, no blocking
        
        block_key = f"rate_limit:blocked:{ip}"
        
        try:
            ttl = await self.cache_service.redis_client.ttl(block_key)
            if ttl and ttl > 0:
                return True, ttl
            return False, 0
        except Exception as e:
            logger.warning(f"Error checking block status for {ip}: {e}")
            return False, 0
    
    async def _block_ip(self, ip: str) -> None:
        """Block an IP address for the configured duration"""
        if not self.cache_service.redis_client:
            return
        
        block_key = f"rate_limit:blocked:{ip}"
        
        try:
            await self.cache_service.redis_client.setex(
                block_key,
                self.block_duration,
                "blocked"
            )
            logger.warning(f"🚫 IP {ip} blocked for {self.block_duration} seconds")
        except Exception as e:
            logger.error(f"Error blocking IP {ip}: {e}")
    
    async def _check_and_increment(self, ip: str) -> Tuple[int, bool]:
        """
        Check current request count and increment.
        
        Returns:
            Tuple of (current_count: int, should_block: bool)
        """
        if not self.cache_service.redis_client:
            return 0, False  # No Redis, no rate limiting
        
        rate_key = f"rate_limit:{ip}"
        
        try:
            # Use pipeline for atomic operations
            pipe = self.cache_service.redis_client.pipeline()
            pipe.incr(rate_key)
            pipe.ttl(rate_key)
            results = await pipe.execute()
            
            count = results[0]
            ttl = results[1]
            
            # Set expiry on first request (ttl will be -1 if no expiry set)
            if ttl == -1:
                await self.cache_service.redis_client.expire(rate_key, 60)  # 60 second window
            
            # Check if limit exceeded
            should_block = count > self.requests_per_minute
            
            return count, should_block
            
        except Exception as e:
            logger.warning(f"Error in rate limit check for {ip}: {e}")
            return 0, False  # On error, allow request


class RateLimiter:
    """
    Utility class for manual rate limiting in specific endpoints.
    
    Usage:
        rate_limiter = RateLimiter()
        await rate_limiter.check_rate_limit(request, limit=10)
    """
    
    def __init__(self):
        self._cache_service = None
    
    @property
    def cache_service(self):
        """Lazy load cache service"""
        if self._cache_service is None:
            from services.cache_service import get_cache
            self._cache_service = get_cache()
        return self._cache_service
    
    async def check_rate_limit(
        self, 
        request: Request, 
        limit: int = 60,
        window: int = 60,
        key_prefix: str = "endpoint"
    ) -> None:
        """
        Check rate limit for a specific endpoint.
        
        Args:
            request: FastAPI request object
            limit: Maximum requests allowed
            window: Time window in seconds
            key_prefix: Prefix for Redis key (e.g., "endpoint:create_item")
            
        Raises:
            HTTPException: If rate limit exceeded
        """
        if not self.cache_service or not self.cache_service.redis_client:
            return  # No Redis, no rate limiting
        
        # Get client IP
        client_ip = request.client.host if request.client else "unknown"
        rate_key = f"rate_limit:{key_prefix}:{client_ip}"
        
        try:
            # Use pipeline for atomic operations
            pipe = self.cache_service.redis_client.pipeline()
            pipe.incr(rate_key)
            pipe.ttl(rate_key)
            results = await pipe.execute()
            
            count = results[0]
            ttl = results[1]
            
            # Set expiry on first request
            if ttl == -1:
                await self.cache_service.redis_client.expire(rate_key, window)
            
            # Check if limit exceeded
            if count > limit:
                actual_ttl = await self.cache_service.redis_client.ttl(rate_key)
                logger.warning(
                    f"⛔ Endpoint rate limit exceeded: {client_ip} on {key_prefix} - "
                    f"{count}/{limit} requests"
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "error": "Rate limit exceeded",
                        "message": f"Too many requests to this endpoint. Try again in {actual_ttl} seconds.",
                        "retry_after": actual_ttl
                    },
                    headers={"Retry-After": str(actual_ttl)}
                )
            
            logger.debug(f"Rate limit check: {client_ip} on {key_prefix} - {count}/{limit}")
            
        except HTTPException:
            raise  # Re-raise HTTPException
        except Exception as e:
            logger.warning(f"Error in endpoint rate limit check: {e}")
            # On error, allow request
