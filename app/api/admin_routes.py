"""
Admin Dashboard API Routes

Provides comprehensive admin endpoints for:
- User management (list, view, edit, deactivate)
- System statistics and monitoring
- Security alerts and audit logs
- Session management across all users
"""
from fastapi import APIRouter, HTTPException, Depends, status, Query
from typing import List, Optional, Dict
from datetime import datetime, timedelta
import logging

from core.auth import get_current_active_user, require_role
from services.user_service import UserService
from services.session_service import get_session_service
from services.token_blacklist_service import get_blacklist_service
from schemas.user import UserResponse, UserUpdate
from db.database import get_db_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin Dashboard"])


# ============================================
# SYSTEM OVERVIEW & STATISTICS
# ============================================

@router.get("/dashboard/overview")
async def get_dashboard_overview(
    current_user: dict = Depends(require_role("admin")),
    session = Depends(get_db_session)
):
    """
    Get comprehensive dashboard overview
    
    **Requires:** Admin role
    
    Returns:
    - User statistics (total, active, by role)
    - Session statistics (active, total)
    - System health metrics
    - Recent activity summary
    """
    try:
        user_service = UserService(session)
        session_service = get_session_service(session)
        blacklist_service = get_blacklist_service()
        
        # Get user statistics
        users_query = "SELECT COUNT(*) as total, COUNT(*) FILTER (WHERE is_active = true) as active FROM users"
        users_stats = await session.fetchrow(users_query)
        
        # Get users by role
        roles_query = """
            SELECT role, COUNT(*) as count 
            FROM users 
            WHERE is_active = true 
            GROUP BY role
        """
        roles_stats = await session.fetch(roles_query)
        
        # Get session statistics
        session_stats = await session_service.get_session_statistics()
        
        # Get blacklist statistics
        blacklist_stats = await blacklist_service.get_blacklist_stats()
        
        # Get recent logins (last 24 hours)
        recent_logins_query = """
            SELECT COUNT(*) as count
            FROM user_sessions
            WHERE created_at > NOW() - INTERVAL '24 hours'
        """
        recent_logins = await session.fetchrow(recent_logins_query)
        
        # Get suspicious login count (last 7 days)
        suspicious_logins_query = """
            SELECT COUNT(*) as count
            FROM user_sessions
            WHERE fingerprint_data::jsonb->'risk_analysis'->>'is_suspicious' = 'true'
            AND created_at > NOW() - INTERVAL '7 days'
        """
        suspicious_logins = await session.fetchrow(suspicious_logins_query)
        
        overview = {
            "timestamp": datetime.utcnow().isoformat(),
            "users": {
                "total": users_stats['total'],
                "active": users_stats['active'],
                "inactive": users_stats['total'] - users_stats['active'],
                "by_role": {row['role']: row['count'] for row in roles_stats}
            },
            "sessions": {
                "active": session_stats['active_sessions'],
                "revoked": session_stats['revoked_sessions'],
                "expired": session_stats['expired_sessions'],
                "unique_users": session_stats['active_users']
            },
            "security": {
                "blacklisted_tokens": blacklist_stats.get('total_blacklisted', 0),
                "logins_24h": recent_logins['count'],
                "suspicious_logins_7d": suspicious_logins['count']
            }
        }
        
        logger.info(f"📊 Dashboard overview requested by admin: {current_user['username']}")
        return overview
    
    except Exception as e:
        logger.error(f"❌ Error fetching dashboard overview: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch dashboard overview"
        )


@router.get("/dashboard/activity")
async def get_recent_activity(
    current_user: dict = Depends(require_role("admin")),
    hours: int = Query(24, description="Hours to look back", ge=1, le=168),
    session = Depends(get_db_session)
):
    """
    Get recent system activity
    
    **Requires:** Admin role
    
    Returns:
    - Recent logins with device info
    - Recent logouts/session revocations
    - Failed login attempts
    - Security alerts
    """
    try:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        # Recent logins
        logins_query = """
            SELECT 
                us.id,
                us.user_id,
                u.username,
                u.email,
                us.device_info,
                us.ip_address,
                us.created_at,
                us.fingerprint_data::jsonb->'risk_analysis'->>'risk_score' as risk_score,
                us.fingerprint_data::jsonb->'risk_analysis'->>'is_suspicious' as is_suspicious
            FROM user_sessions us
            JOIN users u ON us.user_id = u.id
            WHERE us.created_at > $1
            ORDER BY us.created_at DESC
            LIMIT 50
        """
        logins = await session.fetch(logins_query, cutoff)
        
        # Recent session revocations
        revocations_query = """
            SELECT 
                us.id,
                us.user_id,
                u.username,
                us.device_info,
                us.revoked_at,
                us.revoke_reason
            FROM user_sessions us
            JOIN users u ON us.user_id = u.id
            WHERE us.is_revoked = true
            AND us.revoked_at > $1
            ORDER BY us.revoked_at DESC
            LIMIT 50
        """
        revocations = await session.fetch(revocations_query, cutoff)
        
        activity = {
            "time_range_hours": hours,
            "cutoff_time": cutoff.isoformat(),
            "recent_logins": [
                {
                    "session_id": row['id'],
                    "user_id": row['user_id'],
                    "username": row['username'],
                    "email": row['email'],
                    "device": row['device_info'],
                    "ip_address": row['ip_address'],
                    "timestamp": row['created_at'].isoformat(),
                    "risk_score": int(row['risk_score']) if row['risk_score'] else 0,
                    "suspicious": row['is_suspicious'] == 'true' if row['is_suspicious'] else False
                }
                for row in logins
            ],
            "recent_revocations": [
                {
                    "session_id": row['id'],
                    "user_id": row['user_id'],
                    "username": row['username'],
                    "device": row['device_info'],
                    "revoked_at": row['revoked_at'].isoformat(),
                    "reason": row['revoke_reason']
                }
                for row in revocations
            ]
        }
        
        logger.info(f"📊 Recent activity ({hours}h) requested by admin: {current_user['username']}")
        return activity
    
    except Exception as e:
        logger.error(f"❌ Error fetching recent activity: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch recent activity"
        )


# ============================================
# USER MANAGEMENT
# ============================================

@router.get("/users")
async def list_all_users(
    current_user: dict = Depends(require_role("admin")),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    role: Optional[str] = Query(None, description="Filter by role"),
    active_only: bool = Query(False, description="Show only active users"),
    search: Optional[str] = Query(None, description="Search username or email"),
    session = Depends(get_db_session)
):
    """
    List all users with filtering
    
    **Requires:** Admin role
    
    Query Parameters:
    - skip: Offset for pagination
    - limit: Max results per page
    - role: Filter by role (admin, user, readonly)
    - active_only: Show only active users
    - search: Search by username or email
    """
    try:
        user_service = UserService(session)
        
        # Build query dynamically
        conditions = []
        params = []
        param_count = 1
        
        if role:
            conditions.append(f"role = ${param_count}")
            params.append(role)
            param_count += 1
        
        if active_only:
            conditions.append(f"is_active = ${param_count}")
            params.append(True)
            param_count += 1
        
        if search:
            search_param_num = param_count
            conditions.append(f"(username ILIKE ${search_param_num} OR email ILIKE ${search_param_num})")
            params.append(f"%{search}%")
            param_count += 1
        
        where_clause = " AND ".join(conditions) if conditions else "TRUE"
        
        # Add limit and offset to params
        limit_param = param_count
        offset_param = param_count + 1
        params.extend([limit, skip])
        
        query = f"""
            SELECT id, username, email, full_name, role, is_active, created_at, updated_at
            FROM users
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT ${limit_param} OFFSET ${offset_param}
        """
        
        results = await session.fetch(query, *params)
        users = [dict(row) for row in results]
        
        logger.info(
            f"📋 Admin {current_user['username']} listed users "
            f"(filters: role={role}, active_only={active_only}, search={search})"
        )
        
        return users
    
    except Exception as e:
        logger.error(f"❌ Error listing users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list users"
        )


@router.get("/users/{user_id}")
async def get_user_details(
    user_id: int,
    current_user: dict = Depends(require_role("admin")),
    session = Depends(get_db_session)
):
    """
    Get detailed information about a specific user
    
    **Requires:** Admin role
    """
    try:
        user_service = UserService(session)
        user = await user_service.get_by_id(user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found"
            )
        
        logger.info(f"👤 Admin {current_user['username']} viewed user: {user['username']}")
        return user
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error fetching user details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch user details"
        )


@router.put("/users/{user_id}")
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    current_user: dict = Depends(require_role("admin")),
    session = Depends(get_db_session)
):
    """
    Update user information
    
    **Requires:** Admin role
    
    Can update:
    - Full name
    - Role (admin, user, readonly)
    - Active status
    """
    try:
        user_service = UserService(session)
        
        # Check if user exists
        existing_user = await user_service.get_by_id(user_id)
        if not existing_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found"
            )
        
        # Prevent admin from deactivating themselves
        if user_id == int(current_user['user_id']) and user_update.is_active is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate your own admin account"
            )
        
        # Update user
        updated_user = await user_service.update(user_id, user_update)
        
        logger.info(
            f"✏️  Admin {current_user['username']} updated user {existing_user['username']} "
            f"(ID: {user_id})"
        )
        
        return {
            "message": "User updated successfully",
            "user": updated_user
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error updating user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user"
        )


@router.post("/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: int,
    revoke_sessions: bool = Query(True, description="Also revoke all sessions"),
    current_user: dict = Depends(require_role("admin")),
    session = Depends(get_db_session)
):
    """
    Deactivate a user account
    
    **Requires:** Admin role
    
    Options:
    - revoke_sessions: Also logout user from all devices (default: true)
    """
    try:
        user_service = UserService(session)
        
        # Check if user exists
        existing_user = await user_service.get_by_id(user_id)
        if not existing_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found"
            )
        
        # Prevent admin from deactivating themselves
        if user_id == int(current_user['user_id']):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate your own admin account"
            )
        
        # Deactivate user
        await user_service.update(user_id, UserUpdate(is_active=False))
        
        # Optionally revoke all sessions
        revoked_count = 0
        if revoke_sessions:
            session_service = get_session_service(session)
            revoked_count = await session_service.revoke_all_user_sessions(
                user_id=user_id,
                reason="admin_deactivation"
            )
        
        logger.warning(
            f"🚫 Admin {current_user['username']} deactivated user {existing_user['username']} "
            f"(ID: {user_id}, sessions_revoked: {revoked_count})"
        )
        
        return {
            "message": f"User {existing_user['username']} deactivated successfully",
            "user_id": user_id,
            "sessions_revoked": revoked_count
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deactivating user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deactivate user"
        )


@router.post("/users/{user_id}/activate")
async def activate_user(
    user_id: int,
    current_user: dict = Depends(require_role("admin")),
    session = Depends(get_db_session)
):
    """
    Reactivate a deactivated user account
    
    **Requires:** Admin role
    """
    try:
        user_service = UserService(session)
        
        # Check if user exists
        existing_user = await user_service.get_by_id(user_id)
        if not existing_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found"
            )
        
        # Activate user
        await user_service.update(user_id, UserUpdate(is_active=True))
        
        logger.info(
            f"✅ Admin {current_user['username']} reactivated user {existing_user['username']} "
            f"(ID: {user_id})"
        )
        
        return {
            "message": f"User {existing_user['username']} reactivated successfully",
            "user_id": user_id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error activating user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to activate user"
        )


# ============================================
# SESSION MANAGEMENT
# ============================================

@router.get("/sessions/all")
async def get_all_sessions(
    current_user: dict = Depends(require_role("admin")),
    active_only: bool = Query(True, description="Show only active sessions"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    session = Depends(get_db_session)
):
    """
    Get all user sessions across the system
    
    **Requires:** Admin role
    """
    try:
        active_filter = "AND us.is_revoked = FALSE AND us.expires_at > NOW()" if active_only else ""
        
        query = f"""
            SELECT 
                us.id,
                us.user_id,
                u.username,
                u.email,
                us.device_info,
                us.ip_address,
                us.created_at,
                us.last_active,
                us.expires_at,
                us.is_revoked,
                us.fingerprint_data::jsonb->'risk_analysis'->>'risk_score' as risk_score
            FROM user_sessions us
            JOIN users u ON us.user_id = u.id
            WHERE TRUE {active_filter}
            ORDER BY us.last_active DESC
            LIMIT $1 OFFSET $2
        """
        
        results = await session.fetch(query, limit, skip)
        
        sessions = [
            {
                "session_id": row['id'],
                "user_id": row['user_id'],
                "username": row['username'],
                "email": row['email'],
                "device": row['device_info'],
                "ip_address": row['ip_address'],
                "created_at": row['created_at'].isoformat(),
                "last_active": row['last_active'].isoformat(),
                "expires_at": row['expires_at'].isoformat(),
                "is_revoked": row['is_revoked'],
                "risk_score": int(row['risk_score']) if row['risk_score'] else 0
            }
            for row in results
        ]
        
        logger.info(f"📊 Admin {current_user['username']} listed all sessions (active_only={active_only})")
        return {
            "sessions": sessions,
            "count": len(sessions),
            "active_only": active_only
        }
    
    except Exception as e:
        logger.error(f"❌ Error fetching all sessions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch sessions"
        )


@router.delete("/sessions/{session_id}")
async def revoke_session_by_id(
    session_id: int,
    current_user: dict = Depends(require_role("admin")),
    session = Depends(get_db_session)
):
    """
    Revoke a specific session by ID
    
    **Requires:** Admin role
    """
    try:
        session_service = get_session_service(session)
        
        # Get session info before revoking
        session_query = """
            SELECT us.id, us.user_id, u.username, us.device_info
            FROM user_sessions us
            JOIN users u ON us.user_id = u.id
            WHERE us.id = $1
        """
        session_info = await session.fetchrow(session_query, session_id)
        
        if not session_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found"
            )
        
        # Revoke session
        success = await session_service.revoke_session(
            session_id=session_id,
            reason="admin_action"
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to revoke session"
            )
        
        logger.warning(
            f"🚫 Admin {current_user['username']} revoked session {session_id} "
            f"for user {session_info['username']}"
        )
        
        return {
            "message": "Session revoked successfully",
            "session_id": session_id,
            "user": session_info['username'],
            "device": session_info['device_info']
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error revoking session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke session"
        )


# ============================================
# SECURITY MONITORING
# ============================================

@router.get("/security/suspicious-logins")
async def get_suspicious_logins(
    current_user: dict = Depends(require_role("admin")),
    days: int = Query(7, ge=1, le=30, description="Days to look back"),
    min_risk_score: int = Query(50, ge=0, le=100, description="Minimum risk score"),
    session = Depends(get_db_session)
):
    """
    Get suspicious login attempts
    
    **Requires:** Admin role
    
    Returns logins with high risk scores (device fingerprinting detected anomalies)
    """
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        query = """
            SELECT 
                us.id,
                us.user_id,
                u.username,
                u.email,
                us.device_info,
                us.ip_address,
                us.created_at,
                us.fingerprint_data
            FROM user_sessions us
            JOIN users u ON us.user_id = u.id
            WHERE us.created_at > $1
            AND us.fingerprint_data IS NOT NULL
            AND (us.fingerprint_data::jsonb->'risk_analysis'->>'risk_score')::int >= $2
            ORDER BY 
                (us.fingerprint_data::jsonb->'risk_analysis'->>'risk_score')::int DESC,
                us.created_at DESC
            LIMIT 100
        """
        
        results = await session.fetch(query, cutoff, min_risk_score)
        
        suspicious_logins = []
        for row in results:
            fingerprint = row['fingerprint_data']
            risk_analysis = fingerprint.get('risk_analysis', {})
            
            suspicious_logins.append({
                "session_id": row['id'],
                "user_id": row['user_id'],
                "username": row['username'],
                "email": row['email'],
                "device": row['device_info'],
                "ip_address": row['ip_address'],
                "timestamp": row['created_at'].isoformat(),
                "risk_score": risk_analysis.get('risk_score', 0),
                "risk_factors": risk_analysis.get('risk_factors', []),
                "is_suspicious": risk_analysis.get('is_suspicious', False),
                "recommendation": risk_analysis.get('recommendation', '')
            })
        
        logger.info(
            f"🚨 Admin {current_user['username']} viewed suspicious logins "
            f"(days={days}, min_risk={min_risk_score})"
        )
        
        return {
            "time_range_days": days,
            "min_risk_score": min_risk_score,
            "count": len(suspicious_logins),
            "suspicious_logins": suspicious_logins
        }
    
    except Exception as e:
        logger.error(f"❌ Error fetching suspicious logins: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch suspicious logins"
        )


@router.get("/security/user-devices/{user_id}")
async def get_user_devices(
    user_id: int,
    current_user: dict = Depends(require_role("admin")),
    session = Depends(get_db_session)
):
    """
    Get all devices used by a specific user
    
    **Requires:** Admin role
    
    Useful for detecting account sharing or compromised accounts
    """
    try:
        query = """
            SELECT 
                device_info,
                ip_address,
                fingerprint_data,
                COUNT(*) as login_count,
                MAX(created_at) as last_login,
                MAX(last_active) as last_active
            FROM user_sessions
            WHERE user_id = $1
            AND fingerprint_data IS NOT NULL
            GROUP BY device_info, ip_address, fingerprint_data
            ORDER BY last_active DESC
        """
        
        results = await session.fetch(query, user_id)
        
        devices = []
        for row in results:
            fingerprint = row['fingerprint_data']
            
            devices.append({
                "device": row['device_info'],
                "ip_address": row['ip_address'],
                "browser": fingerprint.get('browser', 'Unknown'),
                "os": fingerprint.get('os', 'Unknown'),
                "device_type": fingerprint.get('device_type', 'Unknown'),
                "login_count": row['login_count'],
                "last_login": row['last_login'].isoformat(),
                "last_active": row['last_active'].isoformat()
            })
        
        logger.info(f"📱 Admin {current_user['username']} viewed devices for user_id={user_id}")
        
        return {
            "user_id": user_id,
            "device_count": len(devices),
            "devices": devices
        }
    
    except Exception as e:
        logger.error(f"❌ Error fetching user devices: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch user devices"
        )
