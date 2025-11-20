"""
Auto Token Refresh Middleware

Automatically refreshes JWT tokens that are about to expire.
Adds X-New-Access-Token header to responses when token is refreshed.
"""
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from datetime import datetime, timedelta
import logging

from core.auth import decode_token, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES

logger = logging.getLogger(__name__)

# Refresh token if it expires within this threshold (5 minutes)
TOKEN_REFRESH_THRESHOLD_MINUTES = 5


class AutoTokenRefreshMiddleware(BaseHTTPMiddleware):
    """
    Middleware to automatically refresh JWT tokens before they expire.
    
    How it works:
    1. Extracts JWT token from Authorization header
    2. Checks token expiration time
    3. If token expires within 5 minutes, generates new token
    4. Adds new token to response header: X-New-Access-Token
    5. Frontend can intercept and store new token automatically
    
    Benefits:
    - Prevents 401 errors due to token expiration
    - Seamless user experience (no login interruptions)
    - No extra API calls needed from frontend
    """
    
    async def dispatch(self, request: Request, call_next):
        """
        Process request and add auto-refresh logic.
        """
        # Extract Authorization header
        auth_header = request.headers.get("Authorization")
        
        new_token = None
        
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split("Bearer ")[1]
            
            try:
                # Decode token to check expiration
                payload = decode_token(token)
                
                # Only refresh access tokens (not refresh tokens)
                if payload.get("type") != "refresh":
                    exp_timestamp = payload.get("exp")
                    
                    if exp_timestamp:
                        exp_datetime = datetime.utcfromtimestamp(exp_timestamp)
                        time_until_expiry = exp_datetime - datetime.utcnow()
                        
                        # Check if token expires soon
                        if time_until_expiry < timedelta(minutes=TOKEN_REFRESH_THRESHOLD_MINUTES):
                            # Token is about to expire - generate new one
                            token_data = {
                                "sub": payload.get("sub"),
                                "email": payload.get("email"),
                                "username": payload.get("username"),
                                "role": payload.get("role"),
                                "full_name": payload.get("full_name")
                            }
                            
                            new_token = create_access_token(data=token_data)
                            
                            logger.info(
                                f"🔄 Auto-refreshed token for user: {payload.get('username')} "
                                f"(expires in {int(time_until_expiry.total_seconds() / 60)} minutes)"
                            )
            
            except Exception as e:
                # Token validation failed - let the endpoint handle it
                logger.debug(f"Token validation in middleware failed: {e}")
        
        # Process request
        response = await call_next(request)
        
        # Add new token to response header if generated
        if new_token:
            response.headers["X-New-Access-Token"] = new_token
            logger.debug("✅ New access token added to response header")
        
        return response
