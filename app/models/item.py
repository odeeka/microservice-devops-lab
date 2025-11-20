from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime


class ItemBase(BaseModel):
    """Base item model with common fields"""
    name: str = Field(..., min_length=1, max_length=200, description="Item name")
    description: Optional[str] = Field(None, max_length=1000, description="Item description")
    price: float = Field(..., gt=0, description="Item price (must be positive)")
    category: Optional[str] = Field(None, max_length=100, description="Item category")
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
