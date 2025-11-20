"""User management API routes"""
from fastapi import APIRouter, HTTPException, Depends, Query, status
from typing import List, Optional
import logging

from schemas.user import (
    UserResponse,
    UserCreate,
    UserUpdate,
    UserChangePassword,
    UserStats
)
from services.user_service import UserService
from core.auth import get_current_active_user
from core.permissions import require_admin, require_user, get_current_user_id
from db.models import UserRole
from db.database import get_db_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("", response_model=List[UserResponse])
async def list_users(
    skip: int = Query(0, ge=0, description="Number of users to skip"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of users to return"),
    role: Optional[UserRole] = Query(None, description="Filter by role"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    is_verified: Optional[bool] = Query(None, description="Filter by verification status"),
    current_user: dict = Depends(require_admin),
    session = Depends(get_db_session)
):
    """
    List all users (Admin only)
    
    - **skip**: Pagination offset
    - **limit**: Number of results per page
    - **role**: Filter by user role
    - **is_active**: Filter by active status
    - **is_verified**: Filter by verification status
    """
    try:
        user_service = UserService(session)
        users = await user_service.list_users(
            skip=skip,
            limit=limit,
            role=role,
            is_active=is_active,
            is_verified=is_verified
        )
        
        logger.info(f"✅ Listed {len(users)} users (requested by {current_user.get('username')})")
        return users
    
    except Exception as e:
        logger.error(f"❌ Error listing users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch users"
        )


@router.get("/stats", response_model=UserStats)
async def get_user_stats(
    current_user: dict = Depends(require_admin),
    session = Depends(get_db_session)
):
    """
    Get user statistics (Admin only)
    
    Returns counts of total, active, verified users and breakdown by role
    """
    try:
        user_service = UserService(session)
        stats = await user_service.get_stats()
        
        logger.info(f"✅ User stats retrieved by {current_user.get('username')}")
        return stats
    
    except Exception as e:
        logger.error(f"❌ Error getting user stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch statistics"
        )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    current_user: dict = Depends(get_current_active_user),
    session = Depends(get_db_session)
):
    """
    Get user by ID
    
    Users can only view their own profile unless they are admin
    """
    try:
        # Check if user is viewing their own profile or is admin
        if current_user["user_id"] != user_id and current_user["role"] != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this user"
            )
        
        user_service = UserService(session)
        user = await user_service.get_by_id(user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        logger.info(f"✅ User {user_id} retrieved by {current_user.get('username')}")
        return user
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch user"
        )


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    current_user: dict = Depends(require_admin),
    session = Depends(get_db_session)
):
    """
    Create a new user (Admin only)
    
    - **email**: Valid email address
    - **username**: Unique username
    - **password**: Strong password
    - **role**: User role (admin/user/readonly)
    """
    try:
        user_service = UserService(session)
        user = await user_service.create(user_data)
        
        logger.info(f"✅ User created: {user.username} by {current_user.get('username')}")
        return user
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"❌ Error creating user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user"
        )


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    current_user: dict = Depends(get_current_active_user),
    session = Depends(get_db_session)
):
    """
    Update user information
    
    Users can update their own profile. Admins can update any user.
    Only admins can change roles and active status.
    """
    try:
        is_admin = current_user["role"] == "admin"
        is_own_profile = current_user["user_id"] == user_id
        
        # Check permissions
        if not is_admin and not is_own_profile:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this user"
            )
        
        # Non-admins cannot change role or is_active
        if not is_admin and (user_data.role is not None or user_data.is_active is not None):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can change role or active status"
            )
        
        user_service = UserService(session)
        user = await user_service.update(user_id, user_data)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        logger.info(f"✅ User {user_id} updated by {current_user.get('username')}")
        return user
    
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"❌ Error updating user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user"
        )


@router.post("/{user_id}/change-password")
async def change_password(
    user_id: int,
    password_data: UserChangePassword,
    current_user: dict = Depends(get_current_active_user),
    session = Depends(get_db_session)
):
    """
    Change user password
    
    Users can only change their own password
    """
    try:
        # Users can only change their own password
        if current_user["user_id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to change this password"
            )
        
        user_service = UserService(session)
        success = await user_service.change_password(user_id, password_data)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        logger.info(f"✅ Password changed for user {user_id}")
        return {"message": "Password changed successfully"}
    
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"❌ Error changing password for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to change password"
        )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    current_user: dict = Depends(require_admin),
    session = Depends(get_db_session)
):
    """
    Delete user (soft delete - sets is_active to False)
    
    Admin only. Cannot delete yourself.
    """
    try:
        # Prevent admin from deleting themselves
        if current_user["user_id"] == user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete your own account"
            )
        
        user_service = UserService(session)
        success = await user_service.delete(user_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        logger.info(f"✅ User {user_id} deleted by {current_user.get('username')}")
        return None
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete user"
        )
