"""
Session Management Service

Tracks all active user sessions (JWT tokens) in the database.
Provides functionality to list, revoke, and manage user sessions.
"""
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from asyncpg import Connection

logger = logging.getLogger(__name__)


class SessionService:
    """Manage user sessions in the database"""
    
    def __init__(self, db_session: Connection):
        self.db = db_session
    
    @staticmethod
    def hash_token(token: str) -> str:
        """
        Create SHA256 hash of token for storage
        
        We store token hashes instead of full tokens for security.
        Even if database is compromised, tokens cannot be extracted.
        
        Args:
            token: JWT token string
        
        Returns:
            Hex string of SHA256 hash
        """
        return hashlib.sha256(token.encode()).hexdigest()
    
    async def create_session(
        self,
        user_id: int,
        token: str,
        expires_at: datetime,
        device_info: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        fingerprint_data: Optional[Dict] = None
    ) -> Dict:
        """
        Create a new session record with device fingerprinting
        
        Called on successful login to track the session.
        
        Args:
            user_id: User ID
            token: JWT access token
            expires_at: Token expiration datetime
            device_info: Device name/type (e.g., "Chrome on Windows")
            ip_address: User's IP address
            user_agent: Full user agent string
            fingerprint_data: Device fingerprint and risk analysis data
        
        Returns:
            Session record as dictionary
        """
        try:
            import json
            token_hash = self.hash_token(token)
            
            # Convert fingerprint_data to JSON for JSONB column
            fingerprint_json = json.dumps(fingerprint_data) if fingerprint_data else None
            
            query = """
                INSERT INTO user_sessions 
                    (user_id, session_token, device_info, ip_address, user_agent, 
                     fingerprint_data, expires_at)
                VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7)
                RETURNING id, user_id, session_token, device_info, ip_address, 
                          fingerprint_data, created_at, last_active, expires_at, is_revoked
            """
            
            result = await self.db.fetchrow(
                query,
                user_id,
                token_hash,
                device_info,
                ip_address,
                user_agent,
                fingerprint_json,  # Pass as JSON string, cast to JSONB in query
                expires_at
            )
            
            session = dict(result)
            
            logger.info(
                f"✅ Session created: user_id={user_id} "
                f"device={device_info} ip={ip_address}"
            )
            
            return session
        
        except Exception as e:
            logger.error(f"❌ Error creating session: {e}")
            raise
    
    async def get_session_by_token(self, token: str) -> Optional[Dict]:
        """
        Get session by token hash
        
        Args:
            token: JWT access token
        
        Returns:
            Session record or None if not found
        """
        try:
            token_hash = self.hash_token(token)
            
            query = """
                SELECT id, user_id, session_token, device_info, ip_address, user_agent,
                       created_at, last_active, expires_at, is_revoked, revoked_at, revoke_reason
                FROM user_sessions
                WHERE session_token = $1
            """
            
            result = await self.db.fetchrow(query, token_hash)
            
            if result:
                return dict(result)
            return None
        
        except Exception as e:
            logger.error(f"❌ Error getting session by token: {e}")
            return None
    
    async def get_user_sessions(
        self,
        user_id: int,
        include_revoked: bool = False
    ) -> List[Dict]:
        """
        Get all sessions for a user
        
        Args:
            user_id: User ID
            include_revoked: Include revoked sessions in results
        
        Returns:
            List of session records
        """
        try:
            if include_revoked:
                query = """
                    SELECT id, user_id, device_info, ip_address, user_agent,
                           created_at, last_active, expires_at, is_revoked, 
                           revoked_at, revoke_reason
                    FROM user_sessions
                    WHERE user_id = $1
                    ORDER BY created_at DESC
                """
                results = await self.db.fetch(query, user_id)
            else:
                query = """
                    SELECT id, user_id, device_info, ip_address, user_agent,
                           created_at, last_active, expires_at, is_revoked
                    FROM user_sessions
                    WHERE user_id = $1 
                      AND is_revoked = FALSE
                      AND expires_at > NOW()
                    ORDER BY last_active DESC
                """
                results = await self.db.fetch(query, user_id)
            
            sessions = [dict(row) for row in results]
            
            logger.debug(
                f"📋 Retrieved {len(sessions)} sessions for user_id={user_id}"
            )
            
            return sessions
        
        except Exception as e:
            logger.error(f"❌ Error getting user sessions: {e}")
            return []
    
    async def update_activity(self, token: str) -> bool:
        """
        Update last_active timestamp for session
        
        Called on each authenticated request to track activity.
        
        Args:
            token: JWT access token
        
        Returns:
            True if updated, False otherwise
        """
        try:
            token_hash = self.hash_token(token)
            
            query = """
                UPDATE user_sessions
                SET last_active = NOW()
                WHERE session_token = $1
                  AND is_revoked = FALSE
                  AND expires_at > NOW()
                RETURNING id
            """
            
            result = await self.db.fetchrow(query, token_hash)
            
            if result:
                logger.debug(f"🔄 Session activity updated: session_id={result['id']}")
                return True
            
            return False
        
        except Exception as e:
            logger.error(f"❌ Error updating session activity: {e}")
            return False
    
    async def revoke_session(
        self,
        session_id: int,
        reason: str = "user_logout"
    ) -> bool:
        """
        Revoke a specific session
        
        Args:
            session_id: Session ID to revoke
            reason: Reason for revocation (user_logout, admin_action, security, etc.)
        
        Returns:
            True if revoked, False otherwise
        """
        try:
            query = """
                UPDATE user_sessions
                SET is_revoked = TRUE,
                    revoked_at = NOW(),
                    revoke_reason = $2
                WHERE id = $1
                  AND is_revoked = FALSE
                RETURNING id, user_id, device_info
            """
            
            result = await self.db.fetchrow(query, session_id, reason)
            
            if result:
                logger.info(
                    f"🚫 Session revoked: session_id={result['id']} "
                    f"user_id={result['user_id']} reason={reason}"
                )
                return True
            
            logger.warning(f"⚠️  Session not found or already revoked: id={session_id}")
            return False
        
        except Exception as e:
            logger.error(f"❌ Error revoking session: {e}")
            return False
    
    async def revoke_session_by_token(
        self,
        token: str,
        reason: str = "user_logout"
    ) -> bool:
        """
        Revoke session by token hash
        
        Args:
            token: JWT access token
            reason: Reason for revocation
        
        Returns:
            True if revoked, False otherwise
        """
        try:
            token_hash = self.hash_token(token)
            
            query = """
                UPDATE user_sessions
                SET is_revoked = TRUE,
                    revoked_at = NOW(),
                    revoke_reason = $2
                WHERE session_token = $1
                  AND is_revoked = FALSE
                RETURNING id, user_id
            """
            
            result = await self.db.fetchrow(query, token_hash, reason)
            
            if result:
                logger.info(
                    f"🚫 Session revoked by token: session_id={result['id']} "
                    f"user_id={result['user_id']} reason={reason}"
                )
                return True
            
            return False
        
        except Exception as e:
            logger.error(f"❌ Error revoking session by token: {e}")
            return False
    
    async def revoke_all_user_sessions(
        self,
        user_id: int,
        except_token: Optional[str] = None,
        reason: str = "revoke_all"
    ) -> int:
        """
        Revoke all sessions for a user
        
        Useful for "logout from all devices" functionality or security events.
        
        Args:
            user_id: User ID whose sessions to revoke
            except_token: Optional token to keep active (current session)
            reason: Reason for revocation
        
        Returns:
            Number of sessions revoked
        """
        try:
            if except_token:
                except_token_hash = self.hash_token(except_token)
                query = """
                    UPDATE user_sessions
                    SET is_revoked = TRUE,
                        revoked_at = NOW(),
                        revoke_reason = $3
                    WHERE user_id = $1
                      AND session_token != $2
                      AND is_revoked = FALSE
                      AND expires_at > NOW()
                    RETURNING id
                """
                results = await self.db.fetch(query, user_id, except_token_hash, reason)
            else:
                query = """
                    UPDATE user_sessions
                    SET is_revoked = TRUE,
                        revoked_at = NOW(),
                        revoke_reason = $2
                    WHERE user_id = $1
                      AND is_revoked = FALSE
                      AND expires_at > NOW()
                    RETURNING id
                """
                results = await self.db.fetch(query, user_id, reason)
            
            count = len(results)
            
            logger.warning(
                f"🚫 Revoked {count} sessions for user_id={user_id} reason={reason}"
            )
            
            return count
        
        except Exception as e:
            logger.error(f"❌ Error revoking all user sessions: {e}")
            return 0
    
    async def cleanup_expired_sessions(self, days_old: int = 30) -> int:
        """
        Cleanup old expired sessions from database
        
        Removes sessions that expired more than X days ago.
        This keeps the database clean and improves query performance.
        
        Args:
            days_old: Remove sessions expired more than this many days ago
        
        Returns:
            Number of sessions deleted
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            
            query = """
                DELETE FROM user_sessions
                WHERE expires_at < $1
                RETURNING id
            """
            
            results = await self.db.fetch(query, cutoff_date)
            count = len(results)
            
            if count > 0:
                logger.info(f"🗑️  Cleaned up {count} expired sessions older than {days_old} days")
            
            return count
        
        except Exception as e:
            logger.error(f"❌ Error cleaning up expired sessions: {e}")
            return 0
    
    async def get_active_session_count(self, user_id: int) -> int:
        """
        Get count of active sessions for a user
        
        Args:
            user_id: User ID
        
        Returns:
            Number of active (non-revoked, non-expired) sessions
        """
        try:
            query = """
                SELECT COUNT(*) as count
                FROM user_sessions
                WHERE user_id = $1
                  AND is_revoked = FALSE
                  AND expires_at > NOW()
            """
            
            result = await self.db.fetchrow(query, user_id)
            count = result['count'] if result else 0
            
            logger.debug(f"📊 User {user_id} has {count} active sessions")
            
            return count
        
        except Exception as e:
            logger.error(f"❌ Error getting active session count: {e}")
            return 0
    
    async def get_session_statistics(self) -> Dict:
        """
        Get overall session statistics
        
        Returns:
            Dictionary with session statistics
        """
        try:
            query = """
                SELECT 
                    COUNT(*) FILTER (WHERE is_revoked = FALSE AND expires_at > NOW()) as active_sessions,
                    COUNT(*) FILTER (WHERE is_revoked = TRUE) as revoked_sessions,
                    COUNT(*) FILTER (WHERE expires_at <= NOW()) as expired_sessions,
                    COUNT(DISTINCT user_id) FILTER (WHERE is_revoked = FALSE AND expires_at > NOW()) as active_users,
                    COUNT(*) as total_sessions
                FROM user_sessions
            """
            
            result = await self.db.fetchrow(query)
            
            stats = {
                "active_sessions": result['active_sessions'] or 0,
                "revoked_sessions": result['revoked_sessions'] or 0,
                "expired_sessions": result['expired_sessions'] or 0,
                "active_users": result['active_users'] or 0,
                "total_sessions": result['total_sessions'] or 0,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            logger.info(f"📊 Session stats: {stats['active_sessions']} active, {stats['revoked_sessions']} revoked")
            
            return stats
        
        except Exception as e:
            logger.error(f"❌ Error getting session statistics: {e}")
            return {
                "active_sessions": 0,
                "revoked_sessions": 0,
                "expired_sessions": 0,
                "active_users": 0,
                "total_sessions": 0,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def get_user_fingerprints(self, user_id: int) -> List[Dict]:
        """
        Get all device fingerprints for a user's sessions.
        
        Used for risk analysis when detecting new logins.
        
        Args:
            user_id: User ID
        
        Returns:
            List of fingerprint_data from user's sessions
        """
        try:
            import json
            
            query = """
                SELECT fingerprint_data
                FROM user_sessions
                WHERE user_id = $1
                  AND fingerprint_data IS NOT NULL
                ORDER BY created_at DESC
            """
            
            results = await self.db.fetch(query, user_id)
            
            fingerprints = []
            for row in results:
                if row['fingerprint_data']:
                    # fingerprint_data comes back as dict from asyncpg's JSONB support
                    fp_data = row['fingerprint_data']
                    # If it's a string, parse it; otherwise use as-is
                    if isinstance(fp_data, str):
                        fp_data = json.loads(fp_data)
                    fingerprints.append(fp_data)
            
            logger.debug(
                f"📊 Retrieved {len(fingerprints)} fingerprints for user_id={user_id}"
            )
            
            return fingerprints
        
        except Exception as e:
            logger.error(f"❌ Error getting user fingerprints: {e}")
            return []


def get_session_service(db_session: Connection) -> SessionService:
    """
    Get session service instance
    
    Args:
        db_session: Database connection
    
    Returns:
        SessionService instance
    """
    return SessionService(db_session)
