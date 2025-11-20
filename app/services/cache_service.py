"""Redis-based caching service for application data"""
import json
from typing import Optional, Any
import redis.asyncio as redis
import logging
from config import get_settings

logger = logging.getLogger(__name__)


class CacheService:
    """Simple Redis-based caching service"""
    
    def __init__(self):
        settings = get_settings()
        self.redis_client = None
        try:
            self.redis_client = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5
            )
        except Exception as e:
            logger.warning(f"Failed to initialize Redis: {e}")
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self.redis_client:
            return None
        
        try:
            value = await self.redis_client.get(key)
            if value:
                logger.debug(f"Cache HIT: {key}")
                return json.loads(value)
            logger.debug(f"Cache MISS: {key}")
            return None
        except Exception as e:
            logger.warning(f"Cache get error for key {key}: {e}")
            return None
    
    async def set(self, key: str, value: Any, expire: int = 300) -> bool:
        """
        Set value in cache with expiration
        
        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            expire: TTL in seconds (default 5 minutes)
        """
        if not self.redis_client:
            return False
        
        try:
            # Convert Pydantic models to dicts before caching
            if isinstance(value, list):
                # Handle list of Pydantic models
                serializable_value = [
                    item.model_dump(mode='json') if hasattr(item, 'model_dump') else item
                    for item in value
                ]
            elif hasattr(value, 'model_dump'):
                # Handle single Pydantic model
                serializable_value = value.model_dump(mode='json')
            else:
                # Already JSON-serializable
                serializable_value = value
            
            await self.redis_client.setex(
                key,
                expire,
                json.dumps(serializable_value)
            )
            logger.debug(f"Cache SET: {key} (TTL: {expire}s)")
            return True
        except Exception as e:
            logger.warning(f"Cache set error for key {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if not self.redis_client:
            return False
        
        try:
            result = await self.redis_client.delete(key)
            logger.debug(f"Cache DELETE: {key}")
            return result > 0
        except Exception as e:
            logger.warning(f"Cache delete error for key {key}: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        if not self.redis_client:
            return False
        
        try:
            result = await self.redis_client.exists(key)
            logger.debug(f"Cache EXISTS: {key} = {result > 0}")
            return result > 0
        except Exception as e:
            logger.warning(f"Cache exists error for key {key}: {e}")
            return False
    
    async def ttl(self, key: str) -> int:
        """
        Get remaining time-to-live for key
        
        Returns:
            TTL in seconds, -2 if key doesn't exist, -1 if key has no expiration
        """
        if not self.redis_client:
            return -2
        
        try:
            ttl = await self.redis_client.ttl(key)
            logger.debug(f"Cache TTL: {key} = {ttl}s")
            return ttl
        except Exception as e:
            logger.warning(f"Cache ttl error for key {key}: {e}")
            return -2
    
    async def keys(self, pattern: str) -> list:
        """
        Get all keys matching pattern
        
        Args:
            pattern: Redis key pattern (e.g., "items:*")
        
        Returns:
            List of matching keys
        """
        if not self.redis_client:
            return []
        
        try:
            keys = await self.redis_client.keys(pattern)
            logger.debug(f"Cache KEYS: {pattern} found {len(keys)} keys")
            return keys
        except Exception as e:
            logger.warning(f"Cache keys error for pattern {pattern}: {e}")
            return []
    
    async def clear_pattern(self, pattern: str) -> int:
        """
        Clear all keys matching pattern
        
        Args:
            pattern: Redis key pattern (e.g., "items:*")
        """
        if not self.redis_client:
            return 0
        
        try:
            keys = await self.redis_client.keys(pattern)
            if keys:
                deleted = await self.redis_client.delete(*keys)
                logger.info(f"Cache CLEAR: {pattern} ({deleted} keys deleted)")
                return deleted
            return 0
        except Exception as e:
            logger.warning(f"Cache clear error for pattern {pattern}: {e}")
            return 0
    
    async def ping(self) -> bool:
        """Check if Redis is available"""
        if not self.redis_client:
            return False
        
        try:
            await self.redis_client.ping()
            return True
        except Exception as e:
            logger.warning(f"Redis ping failed: {e}")
            return False
    
    async def close(self):
        """Close Redis connection"""
        if self.redis_client:
            try:
                await self.redis_client.close()
            except Exception as e:
                logger.warning(f"Error closing Redis connection: {e}")


# Singleton cache instance
_cache_instance: Optional[CacheService] = None


def get_cache() -> CacheService:
    """Get or create cache service singleton"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = CacheService()
    return _cache_instance
