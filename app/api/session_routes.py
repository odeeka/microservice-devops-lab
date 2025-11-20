"""Session Management API routes"""
from fastapi import APIRouter, HTTPException, Depends, status, Request
from fastapi.security import HTTPAuthorizationCredentials
from typing import List, Optional
import logging

from services.session_service import SessionService, get_session_service
from services.token_blacklist_service import get_blacklist_service
from core.auth import get_current_active_user, security
from db.database import get_db_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions", tags=["Session Management"])


@router.get("")
async def list_user_sessions(
    current_user: dict = Depends(get_current_active_user),
    session = Depends(get_db_session)
):
    """
    List all active sessions for the current user
    
    Shows all devices/locations where the user is currently logged in.
    Useful for security monitoring and "where you're logged in" functionality.
    
    Returns:
        List of active sessions with device info, IP, last activity
    """
    try:
        session_service = get_session_service(session)
        user_id = int(current_user.get('user_id'))
        
        sessions = await session_service.get_user_sessions(
            user_id=user_id,
            include_revoked=False
        )
        
        # Remove session_token from response for security
        for s in sessions:
            s.pop('session_token', None)
        
        logger.info(
            f"📋 Listed {len(sessions)} active sessions for user: "
            f"{current_user.get('username')}"
        )
        
        return {
            "sessions": sessions,
            "total": len(sessions)
        }
    
    except Exception as e:
        logger.error(f"❌ Error listing user sessions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve sessions"
        )


@router.get("/history")
async def get_session_history(
    current_user: dict = Depends(get_current_active_user),
    session = Depends(get_db_session)
):
    """
    Get complete session history including revoked sessions
    
    Shows all past and current sessions with revocation info.
    """
    try:
        session_service = get_session_service(session)
        user_id = int(current_user.get('user_id'))
        
        sessions = await session_service.get_user_sessions(
            user_id=user_id,
            include_revoked=True
        )
        
        # Remove session_token from response
        for s in sessions:
            s.pop('session_token', None)
        
        logger.info(
            f"📋 Retrieved session history for user: {current_user.get('username')}"
        )
        
        return {
            "sessions": sessions,
            "total": len(sessions)
        }
    
    except Exception as e:
        logger.error(f"❌ Error getting session history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve session history"
        )


@router.get("/active/count")
async def get_active_session_count(
    current_user: dict = Depends(get_current_active_user),
    session = Depends(get_db_session)
):
    """
    Get count of active sessions
    
    Quick endpoint to check how many devices the user is logged in on.
    """
    try:
        session_service = get_session_service(session)
        user_id = int(current_user.get('user_id'))
        
        count = await session_service.get_active_session_count(user_id)
        
        return {
            "active_sessions": count,
            "user_id": user_id
        }
    
    except Exception as e:
        logger.error(f"❌ Error getting active session count: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get session count"
        )


@router.delete("/{session_id}")
async def revoke_session(
    session_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: dict = Depends(get_current_active_user),
    session = Depends(get_db_session)
):
    """
    Revoke a specific session (logout from specific device)
    
    This will:
    - Mark session as revoked in database
    - Blacklist the token in Redis
    - Token can no longer be used for authentication
    
    Useful for "logout from device X" functionality.
    """
    try:
        session_service = get_session_service(session)
        user_id = int(current_user.get('user_id'))
        
        # Get session to verify ownership
        sessions = await session_service.get_user_sessions(user_id, include_revoked=False)
        target_session = next((s for s in sessions if s['id'] == session_id), None)
        
        if not target_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found or already revoked"
            )
        
        # Revoke session in database
        success = await session_service.revoke_session(
            session_id=session_id,
            reason="user_revoke"
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to revoke session"
            )
        
        logger.info(
            f"✅ Session revoked: session_id={session_id} "
            f"user={current_user.get('username')}"
        )
        
        return {
            "message": "Session revoked successfully",
            "session_id": session_id,
            "device": target_session.get('device_info')
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error revoking session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke session"
        )


@router.delete("")
async def revoke_all_sessions(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: dict = Depends(get_current_active_user),
    session = Depends(get_db_session)
):
    """
    Revoke all sessions except the current one
    
    "Logout from all other devices" functionality.
    This will:
    - Revoke all other sessions in database
    - Blacklist all other tokens in Redis
    - Keep current session active
    
    Useful for security events or user wants to ensure only their current device has access.
    """
    try:
        session_service = get_session_service(session)
        user_id = int(current_user.get('user_id'))
        
        # Get current token to exclude it
        current_token = credentials.credentials
        
        # Revoke all sessions except current
        count = await session_service.revoke_all_user_sessions(
            user_id=user_id,
            except_token=current_token,
            reason="revoke_all_other_devices"
        )
        
        logger.warning(
            f"🚫 User {current_user.get('username')} revoked {count} other sessions "
            f"(logout from all devices)"
        )
        
        return {
            "message": f"Successfully logged out from {count} other device(s)",
            "sessions_revoked": count,
            "note": "Your current session remains active"
        }
    
    except Exception as e:
        logger.error(f"❌ Error revoking all sessions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke sessions"
        )


# ==================== ADMIN ENDPOINTS ====================

@router.get("/admin/statistics")
async def get_session_statistics(
    current_user: dict = Depends(get_current_active_user),
    session = Depends(get_db_session)
):
    """
    Get overall session statistics (Admin only)
    
    Returns statistics about all sessions across all users.
    """
    # Check admin permission
    if current_user.get("role") != "admin":
        logger.warning(
            f"❌ Unauthorized access attempt to session stats by "
            f"{current_user.get('username')}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions. Required role: admin"
        )
    
    try:
        session_service = get_session_service(session)
        stats = await session_service.get_session_statistics()
        
        logger.info(
            f"📊 Session statistics requested by admin: {current_user.get('username')}"
        )
        
        return stats
    
    except Exception as e:
        logger.error(f"❌ Error getting session statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve session statistics"
        )


@router.post("/admin/cleanup")
async def cleanup_expired_sessions(
    days_old: int = 30,
    current_user: dict = Depends(get_current_active_user),
    session = Depends(get_db_session)
):
    """
    Cleanup old expired sessions (Admin only)
    
    Removes sessions that expired more than X days ago.
    Helps keep database clean and performant.
    """
    # Check admin permission
    if current_user.get("role") != "admin":
        logger.warning(
            f"❌ Unauthorized access attempt to session cleanup by "
            f"{current_user.get('username')}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions. Required role: admin"
        )
    
    try:
        session_service = get_session_service(session)
        count = await session_service.cleanup_expired_sessions(days_old=days_old)
        
        logger.info(
            f"🗑️  Admin {current_user.get('username')} cleaned up {count} expired sessions"
        )
        
        return {
            "message": f"Cleaned up {count} expired session(s)",
            "sessions_deleted": count,
            "days_old": days_old
        }
    
    except Exception as e:
        logger.error(f"❌ Error cleaning up sessions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cleanup sessions"
        )


@router.delete("/admin/user/{user_id}")
async def revoke_user_sessions(
    user_id: int,
    current_user: dict = Depends(get_current_active_user),
    session = Depends(get_db_session)
):
    """
    Revoke all sessions for a specific user (Admin only)
    
    Force logout a user from all devices.
    Use cases:
    - Account compromise
    - User suspension
    - Security investigation
    """
    # Check admin permission
    if current_user.get("role") != "admin":
        logger.warning(
            f"❌ Unauthorized access attempt to revoke user sessions by "
            f"{current_user.get('username')}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions. Required role: admin"
        )
    
    try:
        session_service = get_session_service(session)
        
        # Revoke all sessions for user
        count = await session_service.revoke_all_user_sessions(
            user_id=user_id,
            except_token=None,  # Revoke ALL sessions
            reason="admin_action"
        )
        
        logger.warning(
            f"🚫 ADMIN ACTION: {current_user.get('username')} revoked "
            f"{count} sessions for user_id={user_id}"
        )
        
        return {
            "message": f"Revoked {count} session(s) for user {user_id}",
            "user_id": user_id,
            "sessions_revoked": count
        }
    
    except Exception as e:
        logger.error(f"❌ Error revoking user sessions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke user sessions"
        )
