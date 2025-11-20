"""JWT-based authentication utilities"""
from datetime import datetime, timedelta
from typing import Optional, Union
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, OAuth2PasswordBearer
import logging

from config import get_settings

logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Token authentication
security = HTTPBearer()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# JWT settings
settings = get_settings()
SECRET_KEY = settings.secret_key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT access token
    
    Args:
        data: Dictionary containing user data (user_id, email, role, etc.)
        expires_delta: Token expiration time (default: 30 minutes)
    
    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    })
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """
    Create JWT refresh token
    
    Args:
        data: Dictionary containing user data
    
    Returns:
        Encoded JWT refresh token
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh"
    })
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> dict:
    """
    Decode and verify JWT token
    
    Args:
        token: JWT token string
    
    Returns:
        Decoded token payload
    
    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        logger.warning(f"JWT decode error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user_from_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    Extract current user from JWT token in Authorization header
    
    Args:
        credentials: HTTP Bearer credentials from request header
    
    Returns:
        Dictionary containing user information
    
    Raises:
        HTTPException: If token is invalid or blacklisted
    """
    from services.token_blacklist_service import get_blacklist_service
    
    token = credentials.credentials
    
    # Check if token is blacklisted (revoked/logged out)
    blacklist_service = get_blacklist_service()
    is_blacklisted = await blacklist_service.is_blacklisted(token)
    
    if is_blacklisted:
        logger.warning("🚫 Attempted use of blacklisted token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked. Please login again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Decode and validate token
    payload = decode_token(token)
    
    # Verify token type
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type"
        )
    
    user_id: str = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )
    
    return {
        "user_id": user_id,
        "email": payload.get("email"),
        "username": payload.get("username"),
        "role": payload.get("role"),
        "full_name": payload.get("full_name")
    }


async def get_current_active_user(current_user: dict = Depends(get_current_user_from_token)) -> dict:
    """
    Get current active user (can be extended to check database)
    
    Args:
        current_user: User information from token
    
    Returns:
        User information
    """
    # Here you could add additional checks like:
    # - Query database to ensure user still exists
    # - Check if user is still active
    # - Update last_seen timestamp
    return current_user


def require_role(required_role: str):
    """
    Dependency to require a specific user role
    
    Args:
        required_role: Required role (admin, user, readonly)
    
    Returns:
        Dependency function that checks user role
    
    Usage:
        @router.get("/admin-only", dependencies=[Depends(require_role("admin"))])
        async def admin_endpoint():
            pass
    """
    async def role_checker(current_user: dict = Depends(get_current_active_user)) -> dict:
        user_role = current_user.get("role", "").lower()
        
        # Admin has access to everything
        if user_role == "admin":
            return current_user
        
        # Check specific role requirement
        if user_role != required_role.lower():
            logger.warning(
                f"❌ Unauthorized access attempt: user {current_user.get('username')} "
                f"(role: {user_role}) tried to access {required_role}-only endpoint"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {required_role}"
            )
        
        return current_user
    
    return role_checker