"""Fake user data generator using asyncpg"""
from faker import Faker
from typing import List, Dict, Any
import logging

from db.models import UserRole
from core.auth import get_password_hash
from db.database import DatabaseManager

logger = logging.getLogger(__name__)
fake = Faker()


class UserGenerator:
    """Generate fake users for testing"""
    
    def __init__(self):
        self.db_manager = DatabaseManager()
    
    async def generate_fake_user(self, role: UserRole = UserRole.USER) -> Dict[str, Any]:
        """Generate a single fake user"""
        first_name = fake.first_name()
        last_name = fake.last_name()
        username = fake.user_name()
        
        return {
            "email": fake.email(),
            "username": username,
            "full_name": f"{first_name} {last_name}",
            "hashed_password": get_password_hash("Password123!"),  # Default password
            "role": role.value,
            "is_active": fake.boolean(chance_of_getting_true=90),
            "is_verified": fake.boolean(chance_of_getting_true=70),
        }
    
    async def create_default_users(self) -> List[Dict[str, Any]]:
        """Create default admin and test users"""
        async with self.db_manager.get_connection() as conn:
            created_users = []
            
            # Check if admin exists
            admin_exists = await conn.fetchval(
                "SELECT COUNT(*) FROM users WHERE email = $1",
                "admin@example.com"
            )
            
            if not admin_exists:
                # Create admin user
                admin = await conn.fetchrow(
                    """
                    INSERT INTO users (email, username, full_name, hashed_password, role, is_active, is_verified)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    RETURNING *
                    """,
                    "admin@example.com",
                    "admin",
                    "System Administrator",
                    get_password_hash("Admin123!"),
                    UserRole.ADMIN.value,
                    True,
                    True
                )
                created_users.append(dict(admin))
                logger.info("✅ Created admin user: admin@example.com / Admin123!")
            
            # Check if test user exists
            user_exists = await conn.fetchval(
                "SELECT COUNT(*) FROM users WHERE email = $1",
                "user@example.com"
            )
            
            if not user_exists:
                # Create regular test user
                test_user = await conn.fetchrow(
                    """
                    INSERT INTO users (email, username, full_name, hashed_password, role, is_active, is_verified)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    RETURNING *
                    """,
                    "user@example.com",
                    "testuser",
                    "Test User",
                    get_password_hash("User123!"),
                    UserRole.USER.value,
                    True,
                    True
                )
                created_users.append(dict(test_user))
                logger.info("✅ Created test user: user@example.com / User123!")
            
            # Check if readonly user exists
            readonly_exists = await conn.fetchval(
                "SELECT COUNT(*) FROM users WHERE email = $1",
                "readonly@example.com"
            )
            
            if not readonly_exists:
                # Create readonly test user
                readonly_user = await conn.fetchrow(
                    """
                    INSERT INTO users (email, username, full_name, hashed_password, role, is_active, is_verified)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    RETURNING *
                    """,
                    "readonly@example.com",
                    "readonly",
                    "Read Only User",
                    get_password_hash("Readonly123!"),
                    UserRole.READONLY.value,
                    True,
                    True
                )
                created_users.append(dict(readonly_user))
                logger.info("✅ Created readonly user: readonly@example.com / Readonly123!")
            
            return created_users
    
    
    async def populate_users(self, count: int = 20) -> int:
        """
        Populate database with fake users
        
        Args:
            count: Number of fake users to create
        
        Returns:
            Number of users created
        """
        # First create default users
        await self.create_default_users()
        
        async with self.db_manager.get_connection() as conn:
            # Check current user count
            current_count = await conn.fetchval("SELECT COUNT(*) FROM users")
            
            logger.info(f"📊 Current user count: {current_count}")
            
            # Calculate how many more users to create
            users_to_create = max(0, count - current_count)
            
            if users_to_create == 0:
                logger.info("ℹ️  Target user count already reached")
                return 0
            
            logger.info(f"🎲 Generating {users_to_create} fake users...")
            
            created_count = 0
            
            for i in range(users_to_create):
                try:
                    # Determine role (80% regular users, 15% readonly, 5% admin)
                    role_chance = fake.random_int(min=1, max=100)
                    if role_chance <= 5:
                        role = UserRole.ADMIN
                    elif role_chance <= 20:
                        role = UserRole.READONLY
                    else:
                        role = UserRole.USER
                    
                    user_data = await self.generate_fake_user(role=role)
                    
                    # Insert user
                    await conn.execute(
                        """
                        INSERT INTO users (email, username, full_name, hashed_password, role, is_active, is_verified)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                        """,
                        user_data["email"],
                        user_data["username"],
                        user_data["full_name"],
                        user_data["hashed_password"],
                        user_data["role"],
                        user_data["is_active"],
                        user_data["is_verified"]
                    )
                    created_count += 1
                    
                    # Log progress every 10 users
                    if (i + 1) % 10 == 0:
                        logger.info(f"  ✅ Created {i + 1}/{users_to_create} users")
                
                except Exception as e:
                    logger.warning(f"  ⚠️  Failed to create user {i + 1}: {e}")
                    continue
            
            logger.info(f"✅ Successfully created {created_count} fake users")
            return created_count
    
    async def get_generation_config(self) -> dict:
        """Get current generation configuration"""
        return {
            "default_password": "Password123!",
            "admin_credentials": "admin@example.com / Admin123!",
            "test_user_credentials": "user@example.com / User123!",
            "readonly_credentials": "readonly@example.com / Readonly123!",
            "role_distribution": {
                "admin": "5%",
                "readonly": "15%",
                "user": "80%"
            }
        }