"""Authentication API routes"""
from fastapi import APIRouter, HTTPException, Depends, status, Request
from fastapi.security import OAuth2PasswordRequestForm, HTTPAuthorizationCredentials, HTTPBearer
from datetime import timedelta, datetime
from typing import Dict, Optional
import logging

from schemas.user import UserLogin, TokenResponse, TokenRefresh, UserCreate, UserResponse
from services.user_service import UserService
from services.token_blacklist_service import get_blacklist_service
from services.session_service import get_session_service
from services.device_fingerprint_service import get_fingerprint_service
from core.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_active_user,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    security
)
from db.database import get_db_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    session = Depends(get_db_session)
):
    """
    Register a new user
    
    - **email**: Valid email address (must be unique)
    - **username**: Username (must be unique, 3-100 characters)
    - **password**: Strong password (min 8 chars, with uppercase, lowercase, and digit)
    - **full_name**: Optional full name
    - **role**: Optional role (defaults to USER)
    """
    try:
        user_service = UserService(session)
        user = await user_service.create(user_data)
        
        logger.info(f"✅ New user registered: {user['username']} ({user['email']})")
        return user
    
    except ValueError as e:
        logger.warning(f"❌ Registration failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"❌ Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register user"
        )


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserLogin,
    request: Request,
    session = Depends(get_db_session)
):
    """
    Login with username/email and password
    
    Returns JWT access token and refresh token.
    Creates a session record to track the login.
    
    - **username**: Username or email address
    - **password**: User password
    """
    try:
        user_service = UserService(session)
        user = await user_service.authenticate(
            credentials.username,
            credentials.password
        )
        
        if not user:
            logger.warning(f"❌ Login failed for: {credentials.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Create access token
        access_token = create_access_token(
            data={
                "sub": str(user['id']),
                "email": user['email'],
                "username": user['username'],
                "role": user['role'],
                "full_name": user['full_name']
            }
        )
        
        # Create refresh token
        refresh_token = create_refresh_token(
            data={
                "sub": str(user['id']),
                "email": user['email']
            }
        )
        
        # Create session record with device fingerprinting
        try:
            session_service = get_session_service(session)
            fingerprint_service = get_fingerprint_service()
            
            # Extract request metadata
            client_host = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent", "Unknown")
            accept_language = request.headers.get("accept-language")
            accept_encoding = request.headers.get("accept-encoding")
            
            # Generate device fingerprint
            fingerprint_data = fingerprint_service.create_fingerprint_data(
                user_agent=user_agent,
                ip_address=client_host,
                accept_language=accept_language,
                accept_encoding=accept_encoding
            )
            
            # Get user's known fingerprints for risk analysis
            known_fingerprints = await session_service.get_user_fingerprints(user['id'])
            
            # Analyze login risk
            risk_analysis = fingerprint_service.analyze_login_risk(
                new_fingerprint=fingerprint_data,
                known_fingerprints=known_fingerprints,
                ip_address=client_host
            )
            
            # Add risk analysis to fingerprint data
            fingerprint_data['risk_analysis'] = risk_analysis
            
            # Log security alerts for suspicious logins
            if risk_analysis['is_suspicious']:
                logger.warning(
                    f"🚨 SUSPICIOUS LOGIN: user={user['username']} "
                    f"risk_score={risk_analysis['risk_score']} "
                    f"factors={', '.join(risk_analysis['risk_factors'])} "
                    f"ip={client_host}"
                )
            
            # Simple device detection from user agent
            device_info = f"{fingerprint_data['browser']} on {fingerprint_data['os']}"
            
            # Calculate token expiration
            expires_at = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
            
            # Create session with fingerprint data
            await session_service.create_session(
                user_id=user['id'],
                token=access_token,
                expires_at=expires_at,
                device_info=device_info,
                ip_address=client_host,
                user_agent=user_agent,
                fingerprint_data=fingerprint_data
            )
            
            logger.info(
                f"✅ User logged in: {user['username']} "
                f"from {client_host} ({device_info}) "
                f"[Risk: {risk_analysis['risk_score']}]"
            )
        except Exception as e:
            # Don't fail login if session creation fails
            logger.error(f"⚠️  Failed to create session record: {e}")
            logger.info(f"✅ User logged in: {user['username']} (session tracking failed)")
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@router.post("/login/form", response_model=TokenResponse)
async def login_form(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session = Depends(get_db_session)
):
    """
    OAuth2 compatible token login (for Swagger UI)
    
    - **username**: Username or email
    - **password**: Password
    """
    try:
        user_service = UserService(session)
        user = await user_service.authenticate(
            form_data.username,
            form_data.password
        )
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        access_token = create_access_token(
            data={
                "sub": str(user['id']),
                "email": user['email'],
                "username": user['username'],
                "role": user['role'],
                "full_name": user['full_name']
            }
        )
        
        refresh_token = create_refresh_token(
            data={
                "sub": str(user['id']),
                "email": user['email']
            }
        )
        
        logger.info(f"✅ User logged in via form: {user['username']}")
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Form login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    token_data: TokenRefresh,
    session = Depends(get_db_session)
):
    """
    Refresh access token using refresh token WITH ROTATION
    
    Security features:
    - Old refresh token is blacklisted (can't be reused)
    - New refresh token is issued with each refresh
    - Detects token reuse attempts and revokes all sessions
    
    - **refresh_token**: Valid refresh token
    """
    try:
        # Decode and verify refresh token
        payload = decode_token(token_data.refresh_token)
        
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        
        # CHECK: Has this refresh token been used before? (Token Reuse Detection)
        blacklist_service = get_blacklist_service()
        if await blacklist_service.is_blacklisted(token_data.refresh_token):
            # SECURITY ALERT: Refresh token reuse detected!
            logger.error(
                f"🚨 SECURITY ALERT: Refresh token reuse detected for user_id={user_id}. "
                f"Revoking all sessions."
            )
            
            # Revoke ALL sessions for this user (security measure)
            try:
                session_service = get_session_service(session)
                revoked_count = await session_service.revoke_all_user_sessions(
                    user_id=int(user_id),
                    except_token=None,  # Revoke ALL
                    reason="refresh_token_reuse_detected"
                )
                logger.warning(f"🚫 Revoked {revoked_count} sessions due to token reuse")
            except Exception as e:
                logger.error(f"Failed to revoke sessions: {e}")
            
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token reuse detected. All sessions have been revoked for security. Please login again."
            )
        
        # Get user from database
        user_service = UserService(session)
        user = await user_service.get_by_id(int(user_id))
        
        if not user or not user['is_active']:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        
        # BLACKLIST the old refresh token (rotation - can't be used again)
        try:
            exp_timestamp = payload.get("exp")
            if exp_timestamp:
                exp_datetime = datetime.utcfromtimestamp(exp_timestamp)
                ttl = int((exp_datetime - datetime.utcnow()).total_seconds())
                
                if ttl > 0:
                    await blacklist_service.blacklist_token(
                        token_data.refresh_token,
                        token_type="refresh"
                    )
                    logger.debug(f"🔄 Old refresh token blacklisted (rotation)")
        except Exception as e:
            logger.warning(f"Failed to blacklist old refresh token: {e}")
        
        # Create new tokens
        access_token = create_access_token(
            data={
                "sub": str(user['id']),
                "email": user['email'],
                "username": user['username'],
                "role": user['role'],
                "full_name": user['full_name']
            }
        )
        
        new_refresh_token = create_refresh_token(
            data={
                "sub": str(user['id']),
                "email": user['email']
            }
        )
        
        logger.info(
            f"✅ Token rotated for user: {user['username']} "
            f"(old refresh token invalidated)"
        )
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,  # NEW refresh token
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Token refresh error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not refresh token"
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    current_user: dict = Depends(get_current_active_user),
    session = Depends(get_db_session)
):
    """
    Get current authenticated user information
    
    Requires valid JWT token in Authorization header
    """
    try:
        user_service = UserService(session)
        user = await user_service.get_by_id(int(current_user["user_id"]))
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return user
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Get current user error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch user"
        )


@router.post("/logout")
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: dict = Depends(get_current_active_user),
    session = Depends(get_db_session)
):
    """
    Logout current user and blacklist their token
    
    This endpoint will:
    - Add the current access token to the blacklist
    - Revoke the session in the database
    - The token will be rejected for all subsequent requests
    """
    blacklist_service = get_blacklist_service()
    
    # Get the access token from the Authorization header
    access_token = credentials.credentials
    
    # Blacklist the access token
    success = await blacklist_service.blacklist_token(access_token, token_type="access")
    
    if not success:
        logger.error(f"❌ Failed to blacklist token for user: {current_user.get('username')}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed. Please try again."
        )
    
    # Revoke session in database
    try:
        session_service = get_session_service(session)
        await session_service.revoke_session_by_token(
            token=access_token,
            reason="user_logout"
        )
    except Exception as e:
        # Don't fail logout if session revocation fails
        logger.error(f"⚠️  Failed to revoke session in database: {e}")
    
    logger.info(
        f"✅ User logged out: {current_user.get('username')} "
        f"(user_id={current_user.get('user_id')})"
    )
    
    return {
        "message": "Successfully logged out",
        "detail": "Your access token has been revoked and can no longer be used."
    }


@router.get("/test")
async def test_auth(current_user: dict = Depends(get_current_active_user)):
    """
    Test authentication - requires valid JWT token
    
    Returns current user information from token
    """
    return {
        "message": "Authentication successful",
        "user": current_user
    }


# ==================== BLACKLIST MANAGEMENT (ADMIN) ====================

@router.get("/blacklist/stats")
async def get_blacklist_stats(current_user: dict = Depends(get_current_active_user)):
    """
    Get token blacklist statistics (Admin only)
    
    Returns information about the number of blacklisted tokens.
    Requires admin role.
    """
    # Check admin permission
    if current_user.get("role") != "admin":
        logger.warning(
            f"❌ Unauthorized access attempt to blacklist stats by "
            f"{current_user.get('username')} (role: {current_user.get('role')})"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions. Required role: admin"
        )
    
    blacklist_service = get_blacklist_service()
    stats = await blacklist_service.get_blacklist_stats()
    
    logger.info(
        f"📊 Blacklist stats requested by admin: {current_user.get('username')}"
    )
    
    return stats


@router.post("/blacklist/remove")
async def remove_from_blacklist(
    token: str,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Remove a token from the blacklist (Admin override)
    
    This is an emergency endpoint to restore access if a token was 
    blacklisted by mistake. Use with caution.
    
    Requires admin role.
    """
    # Check admin permission
    if current_user.get("role") != "admin":
        logger.warning(
            f"❌ Unauthorized access attempt to remove blacklist by "
            f"{current_user.get('username')}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions. Required role: admin"
        )
    
    blacklist_service = get_blacklist_service()
    
    # Get info before removing (for logging)
    info = await blacklist_service.get_blacklist_info(token)
    
    success = await blacklist_service.remove_from_blacklist(token)
    
    if success:
        logger.warning(
            f"⚠️  ADMIN OVERRIDE: Token removed from blacklist by "
            f"{current_user.get('username')} - Previous info: {info}"
        )
        return {
            "message": "Token removed from blacklist",
            "previous_info": info
        }
    else:
        return {
            "message": "Token was not in blacklist",
            "info": None
        }


@router.post("/blacklist/user/{user_id}")
async def blacklist_all_user_tokens(
    user_id: str,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Blacklist all active tokens for a specific user (Admin only)
    
    Use this for security events like:
    - Suspected account compromise
    - Password reset
    - Account suspension
    
    Note: Requires session tracking to be fully implemented.
    Currently returns 0 as placeholder.
    
    Requires admin role.
    """
    # Check admin permission
    if current_user.get("role") != "admin":
        logger.warning(
            f"❌ Unauthorized access attempt to blacklist user tokens by "
            f"{current_user.get('username')}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions. Required role: admin"
        )
    
    blacklist_service = get_blacklist_service()
    count = await blacklist_service.blacklist_all_user_tokens(user_id)
    
    logger.warning(
        f"🚫 ADMIN ACTION: All tokens for user_id={user_id} blacklisted by "
        f"{current_user.get('username')} - Count: {count}"
    )
    
    return {
        "message": f"Blacklisted {count} tokens for user {user_id}",
        "user_id": user_id,
        "tokens_blacklisted": count,
        "note": "Full implementation requires session tracking (coming soon)"
    }
