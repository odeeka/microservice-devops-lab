# Admin Dashboard API Documentation

## Overview

The Admin Dashboard provides comprehensive system management capabilities for administrators. It includes user management, session monitoring, security analytics, and system statistics.

**Base Path:** `/api/v1/admin`  
**Authentication:** Requires admin role (Bearer token)  
**Access Control:** All endpoints enforce RBAC - only users with `admin` role can access

## Table of Contents

1. [Dashboard Overview](#dashboard-overview)
2. [User Management](#user-management)
3. [Session Management](#session-management)
4. [Security Monitoring](#security-monitoring)
5. [Usage Examples](#usage-examples)

---

## Dashboard Overview

### Get Dashboard Overview
Returns comprehensive system statistics including users, sessions, and security metrics.

**Endpoint:** `GET /admin/dashboard/overview`

**Response:**
```json
{
  "timestamp": "2025-11-20T23:00:00.000000",
  "users": {
    "total": 20,
    "active": 16,
    "inactive": 4,
    "by_role": {
      "admin": 2,
      "user": 12,
      "readonly": 2
    }
  },
  "sessions": {
    "active": 6,
    "revoked": 1,
    "expired": 9,
    "unique_users": 1
  },
  "security": {
    "blacklisted_tokens": 1,
    "logins_24h": 15,
    "suspicious_logins_7d": 2
  }
}
```

### Get Recent Activity
Returns recent login and session revocation activity.

**Endpoint:** `GET /admin/dashboard/activity`

**Query Parameters:**
- `hours` (int, default=24): Time range in hours to look back

**Response:**
```json
{
  "time_range_hours": 24,
  "cutoff_time": "2025-11-19T23:00:00.000000",
  "recent_logins": [
    {
      "session_id": 15,
      "user_id": 1,
      "username": "admin",
      "email": "admin@example.com",
      "device": "Chrome on Windows",
      "ip_address": "192.168.1.100",
      "timestamp": "2025-11-20T22:30:00.000000",
      "risk_score": 0,
      "suspicious": false
    }
  ],
  "recent_revocations": [
    {
      "session_id": 12,
      "user_id": 5,
      "username": "testuser",
      "device": "Safari on macOS",
      "revoked_at": "2025-11-20T20:15:00.000000",
      "reason": "Admin revoked session"
    }
  ]
}
```

---

## User Management

### List All Users
Get paginated list of users with filtering options.

**Endpoint:** `GET /admin/users`

**Query Parameters:**
- `skip` (int, default=0): Pagination offset
- `limit` (int, default=50, max=100): Results per page
- `role` (string): Filter by role (admin/user/readonly)
- `active_only` (bool, default=false): Show only active users
- `search` (string): Search username or email (case-insensitive)

**Example Request:**
```bash
GET /admin/users?role=admin&active_only=true&limit=10
```

**Response:**
```json
[
  {
    "id": 1,
    "username": "admin",
    "email": "admin@example.com",
    "full_name": "System Administrator",
    "role": "admin",
    "is_active": true,
    "created_at": "2025-11-20T18:34:38.127184+00:00",
    "updated_at": "2025-11-20T18:34:38.127184+00:00"
  }
]
```

### Get User Details
Retrieve detailed information about a specific user.

**Endpoint:** `GET /admin/users/{user_id}`

**Response:**
```json
{
  "id": 1,
  "username": "admin",
  "email": "admin@example.com",
  "full_name": "System Administrator",
  "role": "admin",
  "is_active": true,
  "is_verified": true,
  "created_at": "2025-11-20T18:34:38.127184+00:00",
  "updated_at": "2025-11-20T18:34:38.127184+00:00"
}
```

### Update User
Update user information (email, username, full_name, role, is_active, is_verified).

**Endpoint:** `PUT /admin/users/{user_id}`

**Request Body:**
```json
{
  "full_name": "Updated Name",
  "role": "user",
  "is_active": true
}
```

**Response:**
```json
{
  "message": "User updated successfully",
  "user": {
    "id": 2,
    "username": "testuser",
    "email": "user@example.com",
    "full_name": "Updated Name",
    "role": "user",
    "is_active": true
  }
}
```

### Deactivate User
Deactivate a user account and optionally revoke all active sessions.

**Endpoint:** `POST /admin/users/{user_id}/deactivate`

**Request Body:**
```json
{
  "reason": "Policy violation",
  "revoke_sessions": true
}
```

**Response:**
```json
{
  "message": "User testuser deactivated successfully",
  "user_id": 2,
  "sessions_revoked": 3
}
```

### Reactivate User
Reactivate a previously deactivated user account.

**Endpoint:** `POST /admin/users/{user_id}/activate`

**Response:**
```json
{
  "message": "User testuser reactivated successfully",
  "user_id": 2
}
```

---

## Session Management

### Get All Sessions
View all user sessions across the system.

**Endpoint:** `GET /admin/sessions/all`

**Query Parameters:**
- `active_only` (bool, default=true): Show only active sessions
- `skip` (int, default=0): Pagination offset
- `limit` (int, default=50, max=200): Results per page

**Response:**
```json
{
  "total": 6,
  "active_sessions": 6,
  "sessions": [
    {
      "session_id": 18,
      "user_id": 1,
      "username": "admin",
      "email": "admin@example.com",
      "device": "Chrome on Windows",
      "ip_address": "192.168.1.100",
      "created_at": "2025-11-20T22:53:43.346421",
      "last_active": "2025-11-20T22:53:43.376637",
      "expires_at": "2025-11-20T23:23:43.346037",
      "is_revoked": false,
      "risk_score": 0
    }
  ]
}
```

### Revoke Session
Administratively revoke a specific session.

**Endpoint:** `DELETE /admin/sessions/{session_id}`

**Response:**
```json
{
  "message": "Session revoked successfully",
  "session_id": 19,
  "user": "admin",
  "device": "Chrome on Windows"
}
```

---

## Security Monitoring

### Get Suspicious Logins
View logins with high risk scores detected by device fingerprinting.

**Endpoint:** `GET /admin/security/suspicious-logins`

**Query Parameters:**
- `days` (int, default=7, max=30): Days to look back
- `min_risk_score` (int, default=50, range=0-100): Minimum risk threshold

**Response:**
```json
{
  "time_range_days": 7,
  "min_risk_score": 50,
  "count": 2,
  "suspicious_logins": [
    {
      "session_id": 11,
      "user_id": 1,
      "username": "admin",
      "email": "admin@example.com",
      "device": "Unknown on Unknown",
      "ip_address": "172.18.0.7",
      "timestamp": "2025-11-20T22:52:33.186561",
      "risk_score": 70,
      "risk_factors": [
        "new_device",
        "different_ip_range"
      ],
      "is_suspicious": true,
      "recommendation": "Require additional verification"
    }
  ]
}
```

### Get User Devices
Track all devices used by a specific user.

**Endpoint:** `GET /admin/security/user-devices/{user_id}`

**Response:**
```json
{
  "user_id": 1,
  "username": "admin",
  "email": "admin@example.com",
  "device_count": 3,
  "devices": [
    {
      "device_fingerprint": "abc123...",
      "device_info": "Chrome on Windows",
      "first_seen": "2025-11-15T10:00:00.000000",
      "last_seen": "2025-11-20T22:53:43.346421",
      "login_count": 45,
      "ip_addresses": ["192.168.1.100", "192.168.1.101"]
    }
  ]
}
```

---

## Usage Examples

### Complete Admin Workflow

#### 1. Check System Status
```bash
curl -X GET "http://localhost/api/v1/admin/dashboard/overview" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

#### 2. Find User by Email
```bash
curl -X GET "http://localhost/api/v1/admin/users?search=john@example.com" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

#### 3. Update User Role
```bash
curl -X PUT "http://localhost/api/v1/admin/users/5" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "role": "admin"
  }'
```

#### 4. Monitor Suspicious Activity
```bash
curl -X GET "http://localhost/api/v1/admin/security/suspicious-logins?days=7&min_risk_score=60" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

#### 5. Revoke Suspicious Session
```bash
curl -X DELETE "http://localhost/api/v1/admin/sessions/42" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

#### 6. Deactivate Compromised Account
```bash
curl -X POST "http://localhost/api/v1/admin/users/5/deactivate" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "Security incident",
    "revoke_sessions": true
  }'
```

---

## Security Features

### Role-Based Access Control (RBAC)
All admin endpoints enforce role-based access control:
- **Admin**: Full access to all endpoints
- **User/Readonly**: Access denied (403 Forbidden)

**Example Error Response:**
```json
{
  "detail": "Access denied. Required role: admin"
}
```

### Audit Logging
All admin actions are logged with:
- Admin username
- Action performed
- Target user/session
- Timestamp
- IP address

### Rate Limiting
Admin endpoints are protected by rate limiting:
- **Limit:** 10 requests per minute per IP
- **Block Duration:** 60 seconds

---

## Testing the Dashboard

Run the comprehensive test suite:

```bash
# Login as admin
TOKEN=$(curl -s -X POST "http://localhost/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"Admin123!"}' | jq -r '.access_token')

# Test dashboard overview
curl -s "http://localhost/api/v1/admin/dashboard/overview" \
  -H "Authorization: Bearer $TOKEN" | jq '.'

# Test user listing
curl -s "http://localhost/api/v1/admin/users?limit=5" \
  -H "Authorization: Bearer $TOKEN" | jq '.'

# Test session management
curl -s "http://localhost/api/v1/admin/sessions/all?active_only=true" \
  -H "Authorization: Bearer $TOKEN" | jq '.'

# Test RBAC (should fail)
USER_TOKEN=$(curl -s -X POST "http://localhost/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"User123!"}' | jq -r '.access_token')

curl -s "http://localhost/api/v1/admin/dashboard/overview" \
  -H "Authorization: Bearer $USER_TOKEN" | jq '.'
```

---

## Error Handling

All endpoints return standard HTTP status codes:

- **200 OK** - Successful operation
- **400 Bad Request** - Invalid input
- **401 Unauthorized** - Missing or invalid token
- **403 Forbidden** - Insufficient permissions
- **404 Not Found** - User/session not found
- **500 Internal Server Error** - Server error

**Error Response Format:**
```json
{
  "detail": "Error message description"
}
```

---

## Best Practices

1. **Regular Monitoring**: Check dashboard overview daily for anomalies
2. **Review Suspicious Logins**: Investigate high-risk login attempts weekly
3. **Session Hygiene**: Revoke stale or suspicious sessions promptly
4. **User Management**: Deactivate inactive accounts after 90 days
5. **Audit Logs**: Review admin action logs for accountability
6. **Device Tracking**: Monitor users with multiple devices or changing IPs
7. **Role Assignments**: Follow principle of least privilege

---

## Related Documentation

- [Authentication Guide](./AUTHENTICATION_GUIDE.md) - JWT authentication and token management
- [Session Management](./SESSION_MANAGEMENT.md) - Session tracking and lifecycle
- [Enhanced Security](./ENHANCED_SECURITY.md) - Device fingerprinting and security features

---

## Support

For issues or questions:
- Check logs: `docker compose logs api --tail 100`
- Review error responses for detailed messages
- Ensure admin role is properly assigned to your user
