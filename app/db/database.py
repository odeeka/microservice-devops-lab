import asyncpg
import os
import logging
from typing import Optional, Any, List
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Singleton database manager with async connection pooling"""
    _instance: Optional['DatabaseManager'] = None
    _pool: Optional[asyncpg.Pool] = None
    _initialized: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def init_db(self):
        """Initialize database connection pool and schema (ASYNC)"""
        if self._initialized:
            logger.info("Database already initialized")
            return

        try:
            logger.info("Initializing async database connection pool...")
            
            # Create ASYNC connection pool with asyncpg
            self._pool = await asyncpg.create_pool(
                host=os.getenv('POSTGRES_HOST', 'localhost'),
                port=int(os.getenv('POSTGRES_PORT', 5432)),
                user=os.getenv('POSTGRES_USER', 'labuser'),
                password=os.getenv('POSTGRES_PASSWORD', 'labpass'),
                database=os.getenv('POSTGRES_DB', 'labdb'),
                min_size=1,
                max_size=20,
                command_timeout=60,
                timeout=30,
                max_queries=50000,
                max_cached_statement_lifetime=300,
                max_cacheable_statement_size=1024 * 15,
            )
            
            # Test connection asynchronously
            async with self._pool.acquire() as conn:
                version = await conn.fetchval("SELECT version()")
                logger.info(f"✅ Connected to PostgreSQL: {version}")
            
            self._initialized = True
            logger.info(f"✅ Async database pool created successfully (min=1, max=20 connections)")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize database pool: {e}")
            raise

    @asynccontextmanager
    async def get_connection(self):
        """Get a connection from the pool (async context manager)"""
        if not self._pool:
            await self.init_db()
        
        async with self._pool.acquire() as connection:
            try:
                yield connection
            except Exception as e:
                logger.error(f"Database operation failed: {e}")
                raise

    async def close_all_connections(self):
        """Close all connections in the pool (async)"""
        if self._pool:
            await self._pool.close()
            self._pool = None
            self._initialized = False
            logger.info("✅ Database connection pool closed gracefully")

    async def execute(self, query: str, *args) -> str:
        """Execute a query without returning results (async)"""
        async with self.get_connection() as conn:
            return await conn.execute(query, *args)

    async def fetch(self, query: str, *args) -> List[asyncpg.Record]:
        """Fetch multiple rows (async)"""
        async with self.get_connection() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args) -> Optional[asyncpg.Record]:
        """Fetch a single row (async)"""
        async with self.get_connection() as conn:
            return await conn.fetchrow(query, *args)

    async def fetchval(self, query: str, *args) -> Any:
        """Fetch a single value (async)"""
        async with self.get_connection() as conn:
            return await conn.fetchval(query, *args)

    async def get_pool_stats(self) -> dict:
        """Get connection pool statistics (async)"""
        if not self._pool:
            return {
                "status": "not_initialized",
                "size": 0,
                "free": 0,
                "in_use": 0,
                "max_size": 0,
                "min_size": 0
            }
        
        return {
            "status": "healthy",
            "size": self._pool.get_size(),
            "free": self._pool.get_idle_size(),
            "in_use": self._pool.get_size() - self._pool.get_idle_size(),
            "max_size": self._pool.get_max_size(),
            "min_size": self._pool.get_min_size(),
        }

    async def execute_transaction(self, queries: List[tuple]) -> bool:
        """
        Execute multiple queries in a transaction (async)
        
        Args:
            queries: List of tuples (query, *args)
            
        Returns:
            bool: True if transaction succeeded
        """
        async with self.get_connection() as conn:
            async with conn.transaction():
                try:
                    for query_data in queries:
                        if isinstance(query_data, tuple):
                            query = query_data[0]
                            args = query_data[1:] if len(query_data) > 1 else ()
                            await conn.execute(query, *args)
                        else:
                            await conn.execute(query_data)
                    return True
                except Exception as e:
                    logger.error(f"Transaction failed: {e}")
                    raise
