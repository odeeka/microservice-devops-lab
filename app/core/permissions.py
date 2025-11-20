"""Role-based access control (RBAC)"""
from functools import wraps
from typing import List
from fastapi import Depends, HTTPException, status
from db.models import UserRole
from core.auth import get_current_active_user
import logging

logger = logging.getLogger(__name__)


class RoleChecker:
    """Dependency to check if user has required role"""
    
    def __init__(self, allowed_roles: List[UserRole]):
        self.allowed_roles = allowed_roles
    
    async def __call__(self, current_user: dict = Depends(get_current_active_user)):
        user_role = current_user.get("role")
        
        # Convert string to UserRole enum if needed
        if isinstance(user_role, str):
            try:
                user_role = UserRole(user_role)
            except ValueError:
                logger.error(f"Invalid role: {user_role}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Invalid user role"
                )
        
        # Admin has access to everything
        if user_role == UserRole.ADMIN:
            return current_user
        
        # Check if user's role is in allowed roles
        if user_role not in self.allowed_roles:
            logger.warning(
                f"Access denied for user {current_user.get('user_id')} "
                f"with role {user_role}. Required: {self.allowed_roles}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {', '.join([r.value for r in self.allowed_roles])}"
            )
        
        return current_user


# Pre-defined role checkers
require_admin = RoleChecker([UserRole.ADMIN])
require_user = RoleChecker([UserRole.USER, UserRole.ADMIN])
require_readonly = RoleChecker([UserRole.READONLY, UserRole.USER, UserRole.ADMIN])


def get_current_user_id(current_user: dict = Depends(get_current_active_user)) -> int:
    """Extract user ID from current user"""
    return current_user["user_id"]


def get_current_user_role(current_user: dict = Depends(get_current_active_user)) -> UserRole:
    """Extract user role from current user"""
    role = current_user["role"]
    if isinstance(role, str):
        return UserRole(role)
    return role