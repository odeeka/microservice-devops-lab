import os
import sys
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
import asyncio

from db.database import DatabaseManager
from models.item import ItemCreate, ItemUpdate, ItemResponse

logger = logging.getLogger(__name__)

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
                INSERT INTO items (name, description, price, category, quantity, is_active)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING *
                """,
                item.name,
                item.description,
                item.price,
                item.category,
                item.quantity,
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

            if item.quantity is not None:
                update_fields.append(f"quantity = ${param_count}")
                params.append(item.quantity)
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
                            INSERT INTO items (name, description, price, category, quantity, is_active)
                            VALUES ($1, $2, $3, $4, $5, $6)
                            RETURNING *
                            """,
                            item.name,
                            item.description,
                            item.price,
                            item.category,
                            item.quantity,
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

    async def place_order(self, items_to_order: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Place an order by reducing item quantities (ASYNC with TRANSACTION)
        
        Args:
            items_to_order: List of dicts with 'item_id' and 'quantity' keys
            
        Returns:
            Dict with success status, message, and details
        """
        try:
            updated_items = []
            errors = []
            
            async with self.db.get_connection() as conn:
                async with conn.transaction():
                    for order_item in items_to_order:
                        item_id = order_item['item_id']
                        quantity_ordered = order_item['quantity']
                        
                        # Get current item
                        row = await conn.fetchrow(
                            "SELECT id, name, quantity FROM items WHERE id = $1 AND is_active = true",
                            item_id
                        )
                        
                        if not row:
                            errors.append(f"Item {item_id} not found or inactive")
                            continue
                        
                        current_quantity = row['quantity']
                        
                        if current_quantity < quantity_ordered:
                            errors.append(f"Insufficient stock for {row['name']}: {current_quantity} available, {quantity_ordered} requested")
                            continue
                        
                        # Update quantity
                        new_quantity = current_quantity - quantity_ordered
                        updated_row = await conn.fetchrow(
                            """
                            UPDATE items 
                            SET quantity = $1, updated_at = $2
                            WHERE id = $3
                            RETURNING id, name, quantity
                            """,
                            new_quantity,
                            datetime.utcnow(),
                            item_id
                        )
                        
                        updated_items.append({
                            'item_id': updated_row['id'],
                            'name': updated_row['name'],
                            'new_quantity': updated_row['quantity'],
                            'ordered': quantity_ordered
                        })
            
            if errors and not updated_items:
                return {
                    'success': False,
                    'message': 'Order failed',
                    'items_updated': 0,
                    'errors': errors
                }
            
            logger.info(f"✅ Order placed: {len(updated_items)} items updated")
            return {
                'success': True,
                'message': f'Order placed successfully: {len(updated_items)} items updated',
                'items_updated': len(updated_items),
                'updated_items': updated_items,
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"❌ Error placing order: {e}")
            raise
