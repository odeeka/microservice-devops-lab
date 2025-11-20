import os
import sys
from fastapi import APIRouter, HTTPException, Query, status
from typing import List, Optional
import logging
from datetime import datetime

from models.item import ItemCreate, ItemUpdate, ItemResponse
from services.item_service import ItemService
from services.data_generator import DataGenerator

# Add the parent directory to Python path for relative imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize service (reuse single instance)
item_service = ItemService()

@router.get("/items", response_model=List[ItemResponse], tags=["Items"])
async def get_items(
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of items to return"),
    category: Optional[str] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Search in name and description"),
    is_active: Optional[bool] = Query(None, description="Filter by active status")
):
    """
    Get all items with optional filtering and pagination (ASYNC).
    
    All database operations are executed asynchronously.
    """
    try:
        items = await item_service.get_all_items(
            skip=skip, 
            limit=limit, 
            category=category, 
            search=search,
            is_active=is_active
        )
        return items
    except Exception as e:
        logger.error(f"Error in get_items: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch items"
        )


@router.get("/items/search", response_model=List[ItemResponse], tags=["Items"])
async def search_items(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(50, ge=1, le=100, description="Maximum results")
):
    """
    Full-text search across items (ASYNC).
    
    Searches in name, description, and category fields.
    """
    try:
        results = await item_service.search_items(q, limit)
        return results
    except Exception as e:
        logger.error(f"Error in search_items: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search failed"
        )


@router.get("/items/{item_id}", response_model=ItemResponse, tags=["Items"])
async def get_item(item_id: int):
    """
    Get a specific item by ID (ASYNC).
    """
    try:
        item = await item_service.get_item_by_id(item_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Item with id {item_id} not found"
            )
        return item
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_item: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch item"
        )


@router.post("/items", response_model=ItemResponse, status_code=status.HTTP_201_CREATED, tags=["Items"])
async def create_item(item: ItemCreate):
    """
    Create a new item (ASYNC).
    """
    try:
        new_item = await item_service.create_item(item)
        return new_item
    except Exception as e:
        logger.error(f"Error in create_item: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create item"
        )


@router.put("/items/{item_id}", response_model=ItemResponse, tags=["Items"])
async def update_item(item_id: int, item: ItemUpdate):
    """
    Update an existing item (ASYNC).
    
    Only provided fields will be updated.
    """
    try:
        updated_item = await item_service.update_item(item_id, item)
        if not updated_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Item with id {item_id} not found"
            )
        return updated_item
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in update_item: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update item"
        )


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Items"])
async def delete_item(
    item_id: int, 
    hard_delete: bool = Query(False, description="Permanently delete item")
):
    """
    Delete an item (ASYNC).
    
    - Default: Soft delete (sets is_active=false)
    - hard_delete=true: Permanently removes from database
    """
    try:
        if hard_delete:
            success = await item_service.hard_delete_item(item_id)
        else:
            success = await item_service.delete_item(item_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Item with id {item_id} not found"
            )
        return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in delete_item: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete item"
        )


@router.get("/items/stats/summary", tags=["Statistics"])
async def get_statistics():
    """
    Get statistical summary of items (ASYNC with CONCURRENT queries).
    
    Uses asyncio.gather() to run multiple database queries in parallel.
    """
    try:
        stats = await item_service.get_statistics()
        return stats
    except Exception as e:
        logger.error(f"Error in get_statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch statistics"
        )


@router.get("/categories", response_model=List[str], tags=["Categories"])
async def get_categories():
    """
    Get all unique item categories (ASYNC).
    """
    try:
        categories = await item_service.get_categories()
        return categories
    except Exception as e:
        logger.error(f"Error in get_categories: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch categories"
        )


@router.post("/items/bulk", response_model=List[ItemResponse], status_code=status.HTTP_201_CREATED, tags=["Items"])
async def bulk_create_items(items: List[ItemCreate]):
    """
    Bulk create multiple items at once (ASYNC with TRANSACTION).
    
    Uses database transaction to ensure atomicity.
    Maximum 100 items per request.
    """
    try:
        if not items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No items provided"
            )
        
        if len(items) > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot create more than 100 items at once"
            )
        
        created_items = await item_service.bulk_create_items(items)
        return created_items
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in bulk_create_items: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to bulk create items"
        )


@router.get("/health/db-pool", tags=["Health"])
async def get_db_pool_stats():
    """
    Get database connection pool statistics (ASYNC).
    
    Useful for monitoring connection pool health.
    """
    try:
        stats = await item_service.db.get_pool_stats()
        return stats
    except Exception as e:
        logger.error(f"Error getting pool stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch pool statistics"
        )


# ============================================
# FAKE DATA GENERATION ENDPOINTS
# ============================================

@router.get("/fake-data/config", tags=["Data Generation"])
async def get_fake_data_config():
    """
    Get current fake data generation configuration
    """
    try:
        generator = DataGenerator()
        config = await generator.get_generation_config()
        return config
    except Exception as e:
        logger.error(f"Error getting fake data config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get configuration"
        )


@router.post("/fake-data/generate", tags=["Data Generation"])
async def generate_fake_data(
    count: Optional[int] = Query(None, ge=1, le=10000, description="Number of items (uses config if not provided)"),
    clear_existing: bool = Query(False, description="Clear existing data first")
):
    """
    Generate fake data on demand
    
    ⚠️ Warning: Set clear_existing=true to delete all existing data!
    """
    from config import get_settings
    settings = get_settings()
    
    # Security check: disable in production
    if not settings.debug and not settings.enable_fake_data:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Fake data generation is disabled in production mode"
        )
    
    try:
        generator = DataGenerator()
        created_count = await generator.populate_database(count, clear_existing)
        
        stats = await item_service.get_statistics()
        
        return {
            "message": f"Successfully generated {created_count} fake items",
            "created": created_count,
            "database_stats": stats
        }
    except Exception as e:
        logger.error(f"Error generating fake data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate fake data: {str(e)}"
        )


@router.get("/fake-data/preview", response_model=List[ItemResponse], tags=["Data Generation"])
async def preview_fake_data(
    count: int = Query(5, ge=1, le=20, description="Number of items to preview"),
    category: Optional[str] = Query(None, description="Specific category")
):
    """
    Preview fake items without saving to database
    """
    try:
        generator = DataGenerator()
        items = generator.generate_items(count, category)
        
        # Convert to response format (with fake IDs and timestamps)
        return [
            ItemResponse(
                id=i + 1,
                name=item.name,
                description=item.description,
                price=item.price,
                category=item.category,
                is_active=item.is_active,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            for i, item in enumerate(items)
        ]
    except Exception as e:
        logger.error(f"Error previewing fake data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to preview fake data"
        )


@router.get("/config", tags=["System"])
async def get_config():
    """
    Get current application configuration (safe values only)
    
    ⚠️ Only available in debug mode
    """
    from config import get_settings
    settings = get_settings()
    
    if not settings.debug:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Configuration endpoint only available in debug mode"
        )
    
    # Return safe configuration (no passwords!)
    return {
        "app": {
            "name": settings.app_name,
            "version": settings.app_version,
            "debug": settings.debug,
            "log_level": settings.log_level,
        },
        "database": {
            "host": settings.postgres_host,
            "port": settings.postgres_port,
            "database": settings.postgres_db,
            "user": settings.postgres_user,
            "pool_min": settings.db_pool_min_size,
            "pool_max": settings.db_pool_max_size,
        },
        "api": {
            "prefix": settings.api_prefix,
            "allowed_hosts": settings.allowed_hosts,
        },
        "monitoring": {
            "metrics_enabled": settings.enable_metrics,
        },
        "fake_data": {
            "enabled": settings.enable_fake_data,
            "count": settings.fake_data_count,
            "only_if_empty": settings.fake_data_only_if_empty,
            "clear_existing": settings.fake_data_clear_existing,
            "active_percentage": settings.fake_data_active_percentage,
        }
    }
