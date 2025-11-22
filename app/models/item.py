from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime


class ItemBase(BaseModel):
    """Base item model with common fields"""
    name: str = Field(..., min_length=1, max_length=200, description="Item name")
    description: Optional[str] = Field(None, max_length=1000, description="Item description")
    price: float = Field(..., gt=0, description="Item price (must be positive)")
    category: Optional[str] = Field(None, max_length=100, description="Item category")
    quantity: int = Field(default=0, ge=0, description="Available quantity in stock")
    is_active: bool = Field(default=True, description="Whether the item is active")


class ItemCreate(ItemBase):
    """Model for creating a new item"""
    pass


class ItemUpdate(BaseModel):
    """Model for updating an existing item (all fields optional)"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    price: Optional[float] = Field(None, gt=0)
    category: Optional[str] = Field(None, max_length=100)
    quantity: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None


class ItemResponse(ItemBase):
    """Model for item responses (includes database fields)"""
    id: int = Field(..., description="Item ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = ConfigDict(from_attributes=True)


class ItemListResponse(BaseModel):
    """Model for paginated item list responses"""
    items: list[ItemResponse]
    total: int
    skip: int
    limit: int

    model_config = ConfigDict(from_attributes=True)


class OrderItem(BaseModel):
    """Model for an item in an order"""
    item_id: int = Field(..., description="Item ID")
    quantity: int = Field(..., gt=0, description="Quantity to order")
    price: float = Field(..., gt=0, description="Price per item")


class OrderCreate(BaseModel):
    """Model for creating an order"""
    items: list[OrderItem] = Field(..., min_length=1, description="Items in the order")
    total: float = Field(..., gt=0, description="Total order amount")


class OrderResponse(BaseModel):
    """Model for order response"""
    success: bool
    message: str
    order_id: Optional[int] = None
    items_updated: int = 0
    errors: list[str] = []
