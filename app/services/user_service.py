"""User service for business logic using asyncpg"""
from typing import Optional, List, Dict, Any
from datetime import datetime
import asyncpg

from db.models import UserRole
from schemas.user import UserCreate, UserUpdate, UserChangePassword
from core.auth import get_password_hash, verify_password
import logging

logger = logging.getLogger(__name__)


class UserService:
    """Service for user-related operations using asyncpg"""
    
    def __init__(self, connection: asyncpg.Connection):
        self.conn = connection
    
    def _row_to_dict(self, row: Optional[asyncpg.Record]) -> Optional[Dict[str, Any]]:
        """Convert asyncpg Record to dictionary"""
        if not row:
            return None
        return dict(row)
    
    async def get_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        query = "SELECT * FROM users WHERE id = $1"
        row = await self.conn.fetchrow(query, user_id)
        return self._row_to_dict(row)
    
    async def get_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email"""
        query = "SELECT * FROM users WHERE LOWER(email) = LOWER($1)"
        row = await self.conn.fetchrow(query, email)
        return self._row_to_dict(row)
    
    async def get_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user by username"""
        query = "SELECT * FROM users WHERE LOWER(username) = LOWER($1)"
        row = await self.conn.fetchrow(query, username)
        return self._row_to_dict(row)
    
    async def get_by_username_or_email(self, identifier: str) -> Optional[Dict[str, Any]]:
        """Get user by username or email"""
        query = """
            SELECT * FROM users 
            WHERE LOWER(username) = LOWER($1) OR LOWER(email) = LOWER($1)
        """
        row = await self.conn.fetchrow(query, identifier)
        return self._row_to_dict(row)
    
    async def create(self, user_data: UserCreate) -> Dict[str, Any]:
        """Create new user"""
        # Check if email already exists
        existing_email = await self.get_by_email(user_data.email)
        if existing_email:
            raise ValueError("Email already registered")
        
        # Check if username already exists
        existing_username = await self.get_by_username(user_data.username)
        if existing_username:
            raise ValueError("Username already taken")
        
        # Create user
        query = """
            INSERT INTO users (email, username, full_name, hashed_password, role, is_active, is_verified)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING *
        """
        row = await self.conn.fetchrow(
            query,
            user_data.email,
            user_data.username,
            user_data.full_name,
            get_password_hash(user_data.password),
            user_data.role.value if user_data.role else UserRole.USER.value,
            True,
            False
        )
        
        user = self._row_to_dict(row)
        logger.info(f"✅ User created: {user['username']} ({user['email']})")
        return user
    
    async def update(self, user_id: int, user_data: UserUpdate) -> Optional[Dict[str, Any]]:
        """Update user"""
        user = await self.get_by_id(user_id)
        if not user:
            return None
        
        # Build update query dynamically
        update_fields = []
        params = []
        param_counter = 1
        
        update_data = user_data.model_dump(exclude_unset=True)
        
        # Check for email conflicts
        if 'email' in update_data:
            existing = await self.get_by_email(update_data['email'])
            if existing and existing['id'] != user_id:
                raise ValueError("Email already in use")
        
        # Check for username conflicts
        if 'username' in update_data:
            existing = await self.get_by_username(update_data['username'])
            if existing and existing['id'] != user_id:
                raise ValueError("Username already taken")
        
        for field, value in update_data.items():
            if field == 'role' and value:
                value = value.value if isinstance(value, UserRole) else value
            update_fields.append(f"{field} = ${param_counter}")
            params.append(value)
            param_counter += 1
        
        if not update_fields:
            return user
        
        params.append(user_id)
        query = f"""
            UPDATE users 
            SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP
            WHERE id = ${param_counter}
            RETURNING *
        """
        
        row = await self.conn.fetchrow(query, *params)
        updated_user = self._row_to_dict(row)
        
        logger.info(f"✅ User updated: {updated_user['username']}")
        return updated_user
    
    async def change_password(
        self, 
        user_id: int, 
        password_data: UserChangePassword
    ) -> bool:
        """Change user password"""
        user = await self.get_by_id(user_id)
        if not user:
            return False
        
        # Verify current password
        if not verify_password(password_data.current_password, user['hashed_password']):
            raise ValueError("Current password is incorrect")
        
        # Update password
        query = """
            UPDATE users 
            SET hashed_password = $1, updated_at = CURRENT_TIMESTAMP
            WHERE id = $2
        """
        await self.conn.execute(
            query,
            get_password_hash(password_data.new_password),
            user_id
        )
        
        logger.info(f"✅ Password changed for user: {user['username']}")
        return True
    
    async def delete(self, user_id: int) -> bool:
        """Delete user (soft delete by setting is_active=False)"""
        user = await self.get_by_id(user_id)
        if not user:
            return False
        
        query = """
            UPDATE users 
            SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
            WHERE id = $1
        """
        await self.conn.execute(query, user_id)
        
        logger.info(f"✅ User deactivated: {user['username']}")
        return True
    
    async def authenticate(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate user with username/email and password"""
        user = await self.get_by_username_or_email(username)
        
        if not user:
            logger.warning(f"❌ Authentication failed: User not found - {username}")
            return None
        
        if not user['is_active']:
            logger.warning(f"❌ Authentication failed: User inactive - {username}")
            return None
        
        if not verify_password(password, user['hashed_password']):
            logger.warning(f"❌ Authentication failed: Invalid password - {username}")
            return None
        
        # Update last login
        query = """
            UPDATE users 
            SET last_login = CURRENT_TIMESTAMP
            WHERE id = $1
        """
        await self.conn.execute(query, user['id'])
        user['last_login'] = datetime.utcnow()
        
        logger.info(f"✅ User authenticated: {user['username']}")
        return user
    
    async def list_users(
        self,
        skip: int = 0,
        limit: int = 10,
        role: Optional[UserRole] = None,
        is_active: Optional[bool] = None,
        is_verified: Optional[bool] = None
    ) -> List[Dict[str, Any]]:
        """List users with filtering"""
        conditions = []
        params = []
        param_counter = 1
        
        if role is not None:
            conditions.append(f"role = ${param_counter}")
            params.append(role.value if isinstance(role, UserRole) else role)
            param_counter += 1
        
        if is_active is not None:
            conditions.append(f"is_active = ${param_counter}")
            params.append(is_active)
            param_counter += 1
        
        if is_verified is not None:
            conditions.append(f"is_verified = ${param_counter}")
            params.append(is_verified)
            param_counter += 1
        
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        
        query = f"""
            SELECT * FROM users
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ${param_counter} OFFSET ${param_counter + 1}
        """
        params.extend([limit, skip])
        
        rows = await self.conn.fetch(query, *params)
        return [dict(row) for row in rows]
    
    async def count_users(
        self,
        role: Optional[UserRole] = None,
        is_active: Optional[bool] = None,
        is_verified: Optional[bool] = None
    ) -> int:
        """Count users with filtering"""
        conditions = []
        params = []
        param_counter = 1
        
        if role is not None:
            conditions.append(f"role = ${param_counter}")
            params.append(role.value if isinstance(role, UserRole) else role)
            param_counter += 1
        
        if is_active is not None:
            conditions.append(f"is_active = ${param_counter}")
            params.append(is_active)
            param_counter += 1
        
        if is_verified is not None:
            conditions.append(f"is_verified = ${param_counter}")
            params.append(is_verified)
            param_counter += 1
        
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        
        query = f"SELECT COUNT(*) FROM users {where_clause}"
        count = await self.conn.fetchval(query, *params)
        return count
    
    async def get_stats(self) -> dict:
        """Get user statistics"""
        total = await self.count_users()
        active = await self.count_users(is_active=True)
        verified = await self.count_users(is_verified=True)
        
        # Count by role
        admin_count = await self.count_users(role=UserRole.ADMIN)
        user_count = await self.count_users(role=UserRole.USER)
        readonly_count = await self.count_users(role=UserRole.READONLY)
        
        return {
            "total_users": total,
            "active_users": active,
            "verified_users": verified,
            "users_by_role": {
                "admin": admin_count,
                "user": user_count,
                "readonly": readonly_count
            }
        }
        
        # Apply filters
        if role is not None:
            query = query.where(User.role == role)
        if is_active is not None:
            query = query.where(User.is_active == is_active)
        if is_verified is not None:
            query = query.where(User.is_verified == is_verified)
        
        result = await self.session.execute(query)
        return result.scalar_one()
    
    async def get_stats(self) -> dict:
        """Get user statistics"""
        total = await self.count_users()
        active = await self.count_users(is_active=True)
        verified = await self.count_users(is_verified=True)
        
        # Count by role
        admin_count = await self.count_users(role=UserRole.ADMIN)
        user_count = await self.count_users(role=UserRole.USER)
        readonly_count = await self.count_users(role=UserRole.READONLY)
        
        return {
            "total_users": total,
            "active_users": active,
            "verified_users": verified,
            "users_by_role": {
                "admin": admin_count,
                "user": user_count,
                "readonly": readonly_count
            }
        }