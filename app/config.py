import os
from typing import Optional, List, Dict, Any, Union
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
import asyncpg
import logging
from contextlib import asynccontextmanager
from datetime import datetime
import asyncio

from db.database import DatabaseManager
from models.item import ItemCreate, ItemUpdate, ItemResponse

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    Priority order:
    1. Environment variables (highest priority)
    2. .env file
    3. Default values (lowest priority)
    """
    
    # ============================================
    # DATABASE SETTINGS
    # ============================================
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "labuser"
    postgres_password: str = "labpass"
    postgres_db: str = "labdb"
    
    # Connection pool settings
    db_pool_min_size: int = 1
    db_pool_max_size: int = 20
    
    # ============================================
    # REDIS SETTINGS
    # ============================================
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    
    # ============================================
    # APPLICATION SETTINGS
    # ============================================
    app_name: str = "Microservice DevOps Lab"
    app_version: str = "1.0.0"
    debug: bool = False
    log_level: str = "INFO"
    log_file: Optional[str] = None
    
    # ============================================
    # API SETTINGS
    # ============================================
    api_prefix: str = "/api/v1"
    
    # Allow string or list for these fields
    allowed_hosts: Union[str, List[str]] = "*"
    allowed_origins: Union[str, List[str]] = "*"
    
    # ============================================
    # SECURITY SETTINGS
    # ============================================
    secret_key: str = "change-me-in-production-min-32-chars"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # ============================================
    # MONITORING SETTINGS
    # ============================================
    enable_metrics: bool = True
    
    # ============================================
    # FAKE DATA GENERATION SETTINGS
    # ============================================
    enable_fake_data: bool = False
    fake_data_count: int = 100
    fake_data_only_if_empty: bool = True
    fake_data_clear_existing: bool = False
    
    # Allow string or list for categories
    fake_data_categories: Union[str, List[str]] = ""
    
    fake_data_active_percentage: float = 0.75
    fake_data_batch_size: int = 50
    
    # ============================================
    # VALIDATORS
    # ============================================
    
    @field_validator('allowed_hosts', mode='before')
    @classmethod
    def parse_allowed_hosts(cls, v) -> List[str]:
        """Parse allowed_hosts from string or list"""
        if isinstance(v, str):
            if v == "*":
                return ["*"]
            return [host.strip() for host in v.split(',') if host.strip()]
        return v if isinstance(v, list) else ["*"]
    
    @field_validator('allowed_origins', mode='before')
    @classmethod
    def parse_allowed_origins(cls, v) -> List[str]:
        """Parse allowed_origins from string or list"""
        if isinstance(v, str):
            if v == "*":
                return ["*"]
            return [origin.strip() for origin in v.split(',') if origin.strip()]
        return v if isinstance(v, list) else ["*"]
    
    @field_validator('fake_data_categories', mode='before')
    @classmethod
    def parse_categories(cls, v) -> List[str]:
        """Parse categories from comma-separated string or list"""
        if isinstance(v, str):
            if not v or v == "":
                return []
            return [cat.strip() for cat in v.split(',') if cat.strip()]
        return v if isinstance(v, list) else []
    
    @field_validator('debug', 'enable_metrics', 'enable_fake_data', 
                     'fake_data_only_if_empty', 'fake_data_clear_existing', mode='before')
    @classmethod
    def parse_bool(cls, v) -> bool:
        """Parse boolean from string values"""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ('true', '1', 'yes', 'on', 't', 'y')
        return bool(v)
    
    # ============================================
    # CONFIGURATION
    # ============================================
    
    model_config = SettingsConfigDict(
        # Load from .env file in project root
        env_file=".env",
        env_file_encoding="utf-8",
        # Case insensitive environment variables
        case_sensitive=False,
        # Ignore extra fields not defined in model
        extra="ignore",
    )
    
    # ============================================
    # COMPUTED PROPERTIES
    # ============================================
    
    @property
    def database_url(self) -> str:
        """Construct async database URL for asyncpg"""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
    
    @property
    def redis_url(self) -> str:
        """Construct Redis connection URL"""
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode"""
        return self.debug
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode"""
        return not self.debug


# Singleton pattern for settings
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """
    Get or create settings singleton instance.
    
    Loads configuration from:
    1. Environment variables (highest priority)
    2. .env file in project root
    3. Default values in Settings class
    
    Returns:
        Settings: Application settings instance
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """
    Force reload settings from environment.
    Useful for testing or configuration changes.
    """
    global _settings
    _settings = None
    return get_settings()

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
        """Initialize database connection pool and schema (async)"""
        if self._initialized:
            logger.info("Database already initialized")
            return

        try:
            # Create async connection pool
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
                # Connection pool optimization settings
                max_queries=50000,  # Max queries per connection before recycling
                max_cached_statement_lifetime=300,  # Cache prepared statements for 5 minutes
                max_cacheable_statement_size=1024 * 15,  # 15KB
            )
            
            # Test connection asynchronously
            async with self._pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            
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
                    for query, *args in queries:
                        await conn.execute(query, *args)
                    return True
                except Exception as e:
                    logger.error(f"Transaction failed: {e}")
                    raise

class ItemService:
    """Business logic for items - All methods are ASYNC"""
    
    def __init__(self):
        self.db = DatabaseManager()

    async def get_all_items(
        self, 
        skip: int = 0, 
        limit: int = 100,
        category: Optional[str] = None,
        search: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> List[ItemResponse]:
        """Get all items with optional filters (ASYNC)"""
        try:
            # Build dynamic query with parameterized values
            query_parts = ["SELECT * FROM items WHERE 1=1"]
            params = []
            param_count = 1

            if category:
                query_parts.append(f"AND category = ${param_count}")
                params.append(category)
                param_count += 1

            if search:
                query_parts.append(f"AND (name ILIKE ${param_count} OR description ILIKE ${param_count})")
                params.append(f"%{search}%")
                param_count += 1

            if is_active is not None:
                query_parts.append(f"AND is_active = ${param_count}")
                params.append(is_active)
                param_count += 1

            query_parts.append(f"ORDER BY created_at DESC LIMIT ${param_count} OFFSET ${param_count + 1}")
            params.extend([limit, skip])

            query = " ".join(query_parts)
            
            # Execute query ASYNCHRONOUSLY
            rows = await self.db.fetch(query, *params)
            
            # Convert to Pydantic models (CPU-bound but lightweight)
            return [ItemResponse(**dict(row)) for row in rows]
            
        except Exception as e:
            logger.error(f"Error fetching items: {e}")
            raise

    async def get_item_by_id(self, item_id: int) -> Optional[ItemResponse]:
        """Get item by ID (ASYNC)"""
        try:
            row = await self.db.fetchrow(
                "SELECT * FROM items WHERE id = $1",
                item_id
            )
            return ItemResponse(**dict(row)) if row else None
            
        except Exception as e:
            logger.error(f"Error fetching item {item_id}: {e}")
            raise

    async def create_item(self, item: ItemCreate) -> ItemResponse:
        """Create a new item (ASYNC)"""
        try:
            row = await self.db.fetchrow(
                """
                INSERT INTO items (name, description, price, category, is_active)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING *
                """,
                item.name,
                item.description,
                item.price,
                item.category,
                item.is_active
            )
            
            logger.info(f"✅ Created item: {row['id']} - {item.name}")
            return ItemResponse(**dict(row))
            
        except Exception as e:
            logger.error(f"❌ Error creating item: {e}")
            raise

    async def update_item(self, item_id: int, item: ItemUpdate) -> Optional[ItemResponse]:
        """Update an existing item (ASYNC)"""
        try:
            # Build dynamic update query
            update_fields = []
            params = []
            param_count = 1

            # Only update fields that are provided (not None)
            if item.name is not None:
                update_fields.append(f"name = ${param_count}")
                params.append(item.name)
                param_count += 1

            if item.description is not None:
                update_fields.append(f"description = ${param_count}")
                params.append(item.description)
                param_count += 1

            if item.price is not None:
                update_fields.append(f"price = ${param_count}")
                params.append(item.price)
                param_count += 1

            if item.category is not None:
                update_fields.append(f"category = ${param_count}")
                params.append(item.category)
                param_count += 1

            if item.is_active is not None:
                update_fields.append(f"is_active = ${param_count}")
                params.append(item.is_active)
                param_count += 1

            if not update_fields:
                # No fields to update, return current item
                return await self.get_item_by_id(item_id)

            # Always update the updated_at timestamp
            update_fields.append(f"updated_at = ${param_count}")
            params.append(datetime.utcnow())
            param_count += 1

            # Add item_id as the last parameter
            params.append(item_id)

            query = f"""
                UPDATE items 
                SET {', '.join(update_fields)}
                WHERE id = ${param_count}
                RETURNING *
            """

            # Execute update ASYNCHRONOUSLY
            row = await self.db.fetchrow(query, *params)
            
            if row:
                logger.info(f"✅ Updated item: {item_id}")
                return ItemResponse(**dict(row))
            return None
            
        except Exception as e:
            logger.error(f"❌ Error updating item {item_id}: {e}")
            raise

    async def delete_item(self, item_id: int) -> bool:
        """Delete an item - soft delete by setting is_active=false (ASYNC)"""
        try:
            result = await self.db.execute(
                "UPDATE items SET is_active = false, updated_at = $1 WHERE id = $2",
                datetime.utcnow(),
                item_id
            )
            
            # Check if any row was affected
            deleted = "UPDATE 1" in result
            if deleted:
                logger.info(f"✅ Soft deleted item: {item_id}")
            return deleted
            
        except Exception as e:
            logger.error(f"❌ Error deleting item {item_id}: {e}")
            raise

    async def hard_delete_item(self, item_id: int) -> bool:
        """Permanently delete an item from database (ASYNC)"""
        try:
            result = await self.db.execute(
                "DELETE FROM items WHERE id = $1",
                item_id
            )
            
            deleted = "DELETE 1" in result
            if deleted:
                logger.info(f"✅ Hard deleted item: {item_id}")
            return deleted
            
        except Exception as e:
            logger.error(f"❌ Error hard deleting item {item_id}: {e}")
            raise

    async def get_statistics(self) -> Dict[str, Any]:
        """
        Get item statistics using CONCURRENT async queries
        
        Uses asyncio.gather() to run multiple queries in parallel
        """
        try:
            # Execute all queries CONCURRENTLY (parallel execution)
            results = await asyncio.gather(
                self.db.fetchval("SELECT COUNT(*) FROM items"),
                self.db.fetchval("SELECT COUNT(*) FROM items WHERE is_active = true"),
                self.db.fetchval("SELECT COUNT(DISTINCT category) FROM items"),
                self.db.fetchval("SELECT AVG(price) FROM items WHERE is_active = true"),
                self.db.fetchval("SELECT MIN(price) FROM items WHERE is_active = true"),
                self.db.fetchval("SELECT MAX(price) FROM items WHERE is_active = true"),
            )
            
            total, active, categories, avg_price, min_price, max_price = results
            
            return {
                "total_items": total or 0,
                "active_items": active or 0,
                "inactive_items": (total or 0) - (active or 0),
                "total_categories": categories or 0,
                "average_price": float(avg_price) if avg_price else 0.0,
                "min_price": float(min_price) if min_price else 0.0,
                "max_price": float(max_price) if max_price else 0.0,
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting statistics: {e}")
            raise

    async def get_categories(self) -> List[str]:
        """Get all unique categories (ASYNC)"""
        try:
            rows = await self.db.fetch(
                "SELECT DISTINCT category FROM items WHERE category IS NOT NULL ORDER BY category"
            )
            return [row['category'] for row in rows]
            
        except Exception as e:
            logger.error(f"❌ Error fetching categories: {e}")
            raise

    async def bulk_create_items(self, items: List[ItemCreate]) -> List[ItemResponse]:
        """
        Bulk create multiple items efficiently using TRANSACTION (ASYNC)
        
        Uses async transaction to ensure atomicity
        """
        try:
            created_items = []
            
            # Use async context manager for connection
            async with self.db.get_connection() as conn:
                # Use async transaction for atomicity
                async with conn.transaction():
                    for item in items:
                        row = await conn.fetchrow(
                            """
                            INSERT INTO items (name, description, price, category, is_active)
                            VALUES ($1, $2, $3, $4, $5)
                            RETURNING *
                            """,
                            item.name,
                            item.description,
                            item.price,
                            item.category,
                            item.is_active
                        )
                        created_items.append(ItemResponse(**dict(row)))
            
            logger.info(f"✅ Bulk created {len(created_items)} items in transaction")
            return created_items
            
        except Exception as e:
            logger.error(f"❌ Error bulk creating items: {e}")
            raise

    async def search_items(self, query: str, limit: int = 50) -> List[ItemResponse]:
        """
        Full-text search across items (ASYNC)
        
        Searches in name, description, and category fields
        """
        try:
            search_pattern = f"%{query}%"
            rows = await self.db.fetch(
                """
                SELECT * FROM items 
                WHERE (
                    name ILIKE $1 OR 
                    description ILIKE $1 OR 
                    category ILIKE $1
                )
                AND is_active = true
                ORDER BY 
                    CASE 
                        WHEN name ILIKE $1 THEN 1
                        WHEN category ILIKE $1 THEN 2
                        ELSE 3
                    END,
                    created_at DESC
                LIMIT $2
                """,
                search_pattern,
                limit
            )
            return [ItemResponse(**dict(row)) for row in rows]
            
        except Exception as e:
            logger.error(f"❌ Error searching items: {e}")
            raise
