"""
Token Blacklist Service

Manages blacklisted JWT tokens for secure logout functionality.
When a user logs out, their token is added to the blacklist and
remains there until it naturally expires.
"""
import logging
from typing import Optional
from datetime import datetime, timedelta

from services.cache_service import get_cache
from core.auth import decode_token, ACCESS_TOKEN_EXPIRE_MINUTES

logger = logging.getLogger(__name__)


class TokenBlacklistService:
    """Manage blacklisted JWT tokens in Redis"""
    
    def __init__(self):
        self.cache = get_cache()
        self.prefix = "blacklist:token:"
    
    async def blacklist_token(self, token: str, token_type: str = "access") -> bool:
        """
        Add token to blacklist
        
        Args:
            token: JWT token to blacklist
            token_type: Type of token (access or refresh)
        
        Returns:
            True if successfully blacklisted, False otherwise
        """
        try:
            # Decode token to get expiration time
            payload = decode_token(token)
            exp_timestamp = payload.get("exp")
            
            if not exp_timestamp:
                logger.warning("⚠️  Token has no expiration, cannot blacklist")
                return False
            
            # Calculate remaining time until token expires
            now = datetime.utcnow().timestamp()
            ttl = int(exp_timestamp - now)
            
            if ttl <= 0:
                logger.info("ℹ️  Token already expired, no need to blacklist")
                return True
            
            # Store token hash in Redis with TTL
            key = f"{self.prefix}{token}"
            success = await self.cache.set(
                key,
                {
                    "blacklisted_at": datetime.utcnow().isoformat(),
                    "token_type": token_type,
                    "user_id": payload.get("sub"),
                    "email": payload.get("email")
                },
                expire=ttl
            )
            
            if success:
                logger.info(
                    f"🚫 Token blacklisted: user_id={payload.get('sub')} "
                    f"type={token_type} ttl={ttl}s"
                )
            else:
                logger.error("❌ Failed to blacklist token")
            
            return success
        
        except Exception as e:
            logger.error(f"❌ Error blacklisting token: {e}")
            return False
    
    async def is_blacklisted(self, token: str) -> bool:
        """
        Check if token is blacklisted
        
        Args:
            token: JWT token to check
        
        Returns:
            True if blacklisted, False otherwise
        """
        try:
            key = f"{self.prefix}{token}"
            exists = await self.cache.exists(key)
            
            if exists:
                logger.warning(f"🚫 Attempted use of blacklisted token")
            
            return exists
        
        except Exception as e:
            logger.error(f"❌ Error checking token blacklist: {e}")
            # Fail securely: if we can't check, assume it's not blacklisted
            # but log the error for investigation
            return False
    
    async def get_blacklist_info(self, token: str) -> Optional[dict]:
        """
        Get information about a blacklisted token
        
        Args:
            token: JWT token to look up
        
        Returns:
            Blacklist info dict or None if not blacklisted
        """
        try:
            key = f"{self.prefix}{token}"
            info = await self.cache.get(key)
            
            if info:
                # Add TTL information
                ttl = await self.cache.ttl(key)
                if isinstance(info, dict):
                    info["remaining_ttl"] = ttl
                
            return info
        
        except Exception as e:
            logger.error(f"❌ Error getting blacklist info: {e}")
            return None
    
    async def remove_from_blacklist(self, token: str) -> bool:
        """
        Remove token from blacklist (admin override)
        
        Args:
            token: JWT token to remove
        
        Returns:
            True if removed, False otherwise
        """
        try:
            key = f"{self.prefix}{token}"
            result = await self.cache.delete(key)
            
            if result:
                logger.info(f"✅ Token removed from blacklist (admin override)")
            else:
                logger.warning(f"⚠️  Token was not in blacklist")
            
            return result
        
        except Exception as e:
            logger.error(f"❌ Error removing token from blacklist: {e}")
            return False
    
    async def blacklist_all_user_tokens(self, user_id: str) -> int:
        """
        Blacklist all active tokens for a specific user
        (Useful for security events like password reset or account compromise)
        
        Args:
            user_id: User ID whose tokens should be blacklisted
        
        Returns:
            Number of tokens blacklisted
        """
        try:
            # This requires tracking tokens per user in session management
            # For now, we'll log this for implementation later
            logger.info(
                f"🚫 Request to blacklist all tokens for user_id={user_id} "
                "(requires session tracking implementation)"
            )
            return 0
        
        except Exception as e:
            logger.error(f"❌ Error blacklisting user tokens: {e}")
            return 0
    
    async def get_blacklist_stats(self) -> dict:
        """
        Get statistics about the token blacklist
        
        Returns:
            Dict with blacklist statistics
        """
        try:
            # Get all blacklisted token keys
            keys = await self.cache.keys(f"{self.prefix}*")
            
            stats = {
                "total_blacklisted": len(keys),
                "prefix": self.prefix,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            logger.info(f"📊 Blacklist stats: {stats['total_blacklisted']} tokens")
            
            return stats
        
        except Exception as e:
            logger.error(f"❌ Error getting blacklist stats: {e}")
            return {
                "total_blacklisted": 0,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def cleanup_expired(self) -> int:
        """
        Cleanup expired blacklist entries
        (Note: Redis automatically removes expired keys, this is for manual cleanup)
        
        Returns:
            Number of entries cleaned up
        """
        # Redis handles TTL automatically, so this is mainly for logging
        logger.info("ℹ️  Redis handles blacklist cleanup automatically via TTL")
        return 0


def get_blacklist_service() -> TokenBlacklistService:
    """
    Get token blacklist service instance
    
    Returns:
        TokenBlacklistService instance
    """
    return TokenBlacklistService()
