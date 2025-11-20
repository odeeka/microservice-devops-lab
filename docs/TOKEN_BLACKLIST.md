# Token Blacklist & Logout Implementation

## Overview

The Token Blacklist system provides secure logout functionality by maintaining a Redis-based list of revoked JWT tokens. When a user logs out, their access token is added to the blacklist and will be rejected for all subsequent requests until its natural expiration.

## Architecture

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ POST /auth/logout
       │ Authorization: Bearer <token>
       ▼
┌─────────────────────────────────────┐
│     FastAPI Application             │
│  ┌───────────────────────────────┐  │
│  │   auth_routes.py              │  │
│  │  - Extract token from header  │  │
│  │  - Call blacklist_token()     │  │
│  └────────────┬──────────────────┘  │
│               ▼                      │
│  ┌───────────────────────────────┐  │
│  │   token_blacklist_service.py  │  │
│  │  - Decode token for exp time  │  │
│  │  - Calculate TTL              │  │
│  │  - Store in Redis with TTL    │  │
│  └────────────┬──────────────────┘  │
│               ▼                      │
│  ┌───────────────────────────────┐  │
│  │   cache_service.py            │  │
│  │  - Redis async operations     │  │
│  │  - set(), get(), exists()     │  │
│  │  - ttl(), keys()              │  │
│  └────────────┬──────────────────┘  │
└────────────────┼──────────────────────┘
                 ▼
        ┌────────────────┐
        │  Redis 7.2.0   │
        │  Key Pattern:  │
        │  blacklist:    │
        │    token:      │
        │    <jwt_token> │
        │  TTL: ~30min   │
        └────────────────┘

For subsequent requests:
┌─────────────┐
│   Client    │ GET /auth/me
└──────┬──────┘ Authorization: Bearer <token>
       ▼
┌─────────────────────────────────────┐
│   get_current_user_from_token()     │
│  1. Check if token is blacklisted   │
│     - Call is_blacklisted(token)    │
│     - Query Redis with exists(key)  │
│  2. If blacklisted:                 │
│     - Raise 401 Unauthorized        │
│     - "Token has been revoked"      │
│  3. If not blacklisted:             │
│     - Continue normal validation    │
│     - Decode JWT and verify         │
└─────────────────────────────────────┘
```

## Components

### 1. Cache Service (`app/services/cache_service.py`)

Redis wrapper with async operations for token blacklist storage.

**Key Methods:**
- `get(key)` - Get value from cache with JSON deserialization
- `set(key, value, expire=300)` - Store value with TTL (default 5 minutes)
- `delete(key)` - Remove key from cache
- `exists(key)` - Check if key exists (returns bool)
- `ttl(key)` - Get remaining time-to-live in seconds
- `keys(pattern)` - Find all keys matching pattern
- `ping()` - Check Redis connectivity

**Configuration:**
- Connection URL from environment: `REDIS_URL=redis://redis:6379`
- Automatic JSON serialization/deserialization
- Connection timeout: 5 seconds
- Graceful error handling (returns None/False on failure)

### 2. Token Blacklist Service (`app/services/token_blacklist_service.py`)

High-level service for managing blacklisted tokens.

**Key Methods:**

#### `blacklist_token(token, token_type="access")`
Adds token to blacklist with automatic TTL calculation.

- Decodes JWT to extract expiration time
- Calculates remaining TTL (exp - now)
- Stores in Redis: `blacklist:token:{jwt_token}`
- Returns `True` if successful, `False` otherwise

**Stored Data:**
```json
{
  "blacklisted_at": "2025-11-20T20:35:22.791317",
  "token_type": "access",
  "user_id": "1",
  "email": "admin@example.com"
}
```

#### `is_blacklisted(token)`
Checks if token is currently blacklisted.

- Queries Redis with `exists(key)`
- Returns `True` if blacklisted, `False` otherwise
- Logs warning on attempted use of blacklisted token

#### `get_blacklist_info(token)`
Retrieves metadata about a blacklisted token.

Returns:
```json
{
  "blacklisted_at": "2025-11-20T20:35:22.791317",
  "token_type": "access",
  "user_id": "1",
  "email": "admin@example.com",
  "remaining_ttl": 1571
}
```

#### `get_blacklist_stats()`
Gets statistics about the blacklist.

Returns:
```json
{
  "total_blacklisted": 2,
  "prefix": "blacklist:token:",
  "timestamp": "2025-11-20T20:38:04.400415"
}
```

#### `remove_from_blacklist(token)` (Admin Only)
Emergency override to remove token from blacklist.

- Use with caution - security risk
- Logs warning with admin username
- Returns `True` if removed, `False` if not in blacklist

#### `blacklist_all_user_tokens(user_id)` (Placeholder)
Future implementation: Blacklist all active tokens for a user.

- Requires session tracking (Phase 2)
- Use cases: Account compromise, password reset, suspension
- Currently returns 0 as placeholder

### 3. Authentication Middleware (`app/core/auth.py`)

Modified `get_current_user_from_token()` to check blacklist before validation.

**Flow:**
1. Extract token from `Authorization: Bearer` header
2. **NEW:** Check if token is blacklisted
   - Call `is_blacklisted(token)`
   - If blacklisted: Raise `401 Unauthorized` with message "Token has been revoked. Please login again."
3. Decode and verify JWT token
4. Verify token type is "access"
5. Extract user information from payload
6. Return user dictionary

**Error Responses:**
```json
{
  "detail": "Token has been revoked. Please login again."
}
```

### 4. Logout Endpoint (`app/api/auth_routes.py`)

Updated logout endpoint to actually blacklist tokens.

**Endpoint:** `POST /api/v1/auth/logout`

**Authentication:** Requires valid JWT token

**Behavior:**
1. Extract access token from Authorization header
2. Call `blacklist_token(token, token_type="access")`
3. Return success or error response

**Success Response (200 OK):**
```json
{
  "message": "Successfully logged out",
  "detail": "Your access token has been revoked and can no longer be used."
}
```

**Error Response (500):**
```json
{
  "detail": "Logout failed. Please try again."
}
```

## Admin Endpoints

### Get Blacklist Statistics

**Endpoint:** `GET /api/v1/auth/blacklist/stats`

**Authorization:** Admin role required

**Response:**
```json
{
  "total_blacklisted": 2,
  "prefix": "blacklist:token:",
  "timestamp": "2025-11-20T20:38:04.400415"
}
```

**Error Response (403 Forbidden):**
```json
{
  "detail": "Insufficient permissions. Required role: admin"
}
```

### Remove Token from Blacklist (Emergency Override)

**Endpoint:** `POST /api/v1/auth/blacklist/remove`

**Authorization:** Admin role required

**Request Body:**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIs..."
}
```

**Response:**
```json
{
  "message": "Token removed from blacklist",
  "previous_info": {
    "blacklisted_at": "2025-11-20T20:35:22.791317",
    "token_type": "access",
    "user_id": "1",
    "email": "admin@example.com",
    "remaining_ttl": 1200
  }
}
```

### Blacklist All User Tokens (Security Event)

**Endpoint:** `POST /api/v1/auth/blacklist/user/{user_id}`

**Authorization:** Admin role required

**Response:**
```json
{
  "message": "Blacklisted 0 tokens for user 1",
  "user_id": "1",
  "tokens_blacklisted": 0,
  "note": "Full implementation requires session tracking (coming soon)"
}
```

## Testing

### Complete Logout Flow

```bash
# 1. Login and get token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"Admin123!"}' | jq -r '.access_token')

echo "Token: $TOKEN"

# 2. Use token (should work)
curl -s -X GET http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer $TOKEN" | jq '.username, .role'
# Output: "admin" "admin"

# 3. Logout (blacklist token)
curl -s -X POST http://localhost:8000/api/v1/auth/logout \
  -H "Authorization: Bearer $TOKEN" | jq .
# Output: {"message": "Successfully logged out", ...}

# 4. Try using same token (should fail with 401)
curl -s -X GET http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer $TOKEN" | jq .
# Output: {"detail": "Token has been revoked. Please login again."}
```

### Get Blacklist Statistics (Admin)

```bash
# Login as admin
ADMIN_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"Admin123!"}' | jq -r '.access_token')

# Get stats
curl -s -X GET http://localhost:8000/api/v1/auth/blacklist/stats \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq .
# Output: {"total_blacklisted": 2, "prefix": "blacklist:token:", ...}
```

### Test RBAC Enforcement

```bash
# Login as regular user
USER_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"User123!"}' | jq -r '.access_token')

# Try to access admin endpoint (should fail with 403)
curl -s -X GET http://localhost:8000/api/v1/auth/blacklist/stats \
  -H "Authorization: Bearer $USER_TOKEN" | jq .
# Output: {"detail": "Insufficient permissions. Required role: admin"}
```

### Verify Redis Storage

```bash
# Check blacklisted tokens
docker exec docker-redis-1 redis-cli KEYS "blacklist:token:*"

# Get token metadata
docker exec docker-redis-1 redis-cli GET "blacklist:token:eyJhbGc..." | jq .

# Check TTL (remaining seconds until expiration)
docker exec docker-redis-1 redis-cli TTL "blacklist:token:eyJhbGc..."
# Output: 1571 (approximately 26 minutes)
```

## Redis Key Structure

### Key Pattern
```
blacklist:token:{jwt_token}
```

### Example Key
```
blacklist:token:eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZW1haWwiOiJhZG1pbkBleGFtcGxlLmNvbSIsInVzZXJuYW1lIjoiYWRtaW4iLCJyb2xlIjoiYWRtaW4iLCJmdWxsX25hbWUiOiJTeXN0ZW0gQWRtaW5pc3RyYXRvciIsImV4cCI6MTc2MzY3MjcyMiwiaWF0IjoxNzYzNjcwOTIyLCJ0eXBlIjoiYWNjZXNzIn0.ITDiRcZCOoys-rsBUmQT2SeZAmsHXVLEz7z7a1x_FWw
```

### Value (JSON)
```json
{
  "blacklisted_at": "2025-11-20T20:35:22.791317",
  "token_type": "access",
  "user_id": "1",
  "email": "admin@example.com"
}
```

### TTL (Time To Live)
- Automatically calculated from JWT `exp` claim
- Typically ~30 minutes for access tokens
- Redis automatically removes expired keys
- No manual cleanup required

## Security Considerations

### 1. Token Lifetime
- **Access tokens:** 30 minutes (configurable in `core/auth.py`)
- **Refresh tokens:** 7 days (not currently blacklisted on logout)
- Blacklist automatically expires with token TTL

### 2. Redis Security
- Redis should not be exposed to public internet
- Use Redis password authentication in production
- Consider Redis ACLs for fine-grained access control
- Enable Redis persistence (AOF/RDB) for durability

### 3. Attack Vectors Mitigated
✅ **Token Reuse After Logout:** Tokens blacklisted on logout
✅ **Unauthorized Admin Access:** RBAC enforced on all endpoints
✅ **Token Replay:** Blacklisted tokens rejected immediately
✅ **Concurrent Sessions:** Each login creates new token (old tokens still valid until expiration or logout)

### 4. Remaining Vulnerabilities
⚠️ **Refresh Token Not Blacklisted:** Refresh tokens remain valid after logout (requires enhancement)
⚠️ **No Session Tracking:** Cannot list or revoke all user sessions (Phase 2 feature)
⚠️ **Token Theft Before Logout:** If attacker steals token before user logs out, they can use it until logout
⚠️ **Short Token Lifetime Tradeoff:** Short TTL improves security but increases login frequency

## Performance Considerations

### Redis Operations
- **Write (logout):** O(1) - Single SET operation with TTL
- **Read (authentication):** O(1) - Single EXISTS operation
- **Stats:** O(N) - KEYS operation (avoid in high-traffic scenarios)

### Optimization Tips
1. **Connection Pooling:** Redis async client uses connection pool
2. **Pipeline Operations:** Consider batching multiple checks
3. **Bloom Filter:** For high-traffic APIs, consider Bloom filter for faster negative checks
4. **TTL Strategy:** Shorter token lifetime = fewer blacklist entries = less memory

### Memory Usage
- **Per blacklisted token:** ~200-300 bytes (key + value)
- **1000 blacklisted tokens:** ~250 KB
- **1 million tokens:** ~250 MB
- Redis automatically evicts expired keys

## Monitoring & Logging

### Application Logs

**Successful logout:**
```
2025-11-20 20:35:22 - services.token_blacklist_service - INFO - 🚫 Token blacklisted: user_id=1 type=access ttl=1799s
2025-11-20 20:35:22 - api.auth_routes - INFO - ✅ User logged out: admin (user_id=1)
```

**Attempted use of blacklisted token:**
```
2025-11-20 20:35:23 - services.token_blacklist_service - WARNING - 🚫 Attempted use of blacklisted token
2025-11-20 20:35:23 - core.auth - WARNING - 🚫 Attempted use of blacklisted token
```

**Admin blacklist stats access:**
```
2025-11-20 20:38:04 - api.auth_routes - INFO - 📊 Blacklist stats requested by admin: admin
```

**Unauthorized access attempt:**
```
2025-11-20 20:38:30 - api.auth_routes - WARNING - ❌ Unauthorized access attempt to blacklist stats by testuser (role: user)
```

### Metrics to Monitor

1. **Blacklist Size:** `blacklist_stats.total_blacklisted`
2. **Logout Rate:** Count of successful `/auth/logout` calls
3. **Rejected Token Rate:** Count of 401 responses with "Token has been revoked"
4. **Redis Connection Health:** Monitor `cache.ping()` failures
5. **Redis Memory Usage:** Track Redis `INFO memory` output

### Prometheus Metrics (Recommended)

```python
# Add to metrics.py
from prometheus_client import Counter, Gauge

logout_total = Counter('auth_logout_total', 'Total logout attempts')
logout_success = Counter('auth_logout_success', 'Successful logouts')
blacklist_check_total = Counter('auth_blacklist_check_total', 'Total blacklist checks')
blacklist_hit = Counter('auth_blacklist_hit', 'Blacklisted token access attempts')
blacklist_size = Gauge('auth_blacklist_size', 'Number of blacklisted tokens')
```

## Troubleshooting

### Issue: Token still works after logout

**Symptoms:**
- User logs out successfully
- Same token can still access protected endpoints

**Diagnosis:**
```bash
# Check if token is in Redis
docker exec docker-redis-1 redis-cli GET "blacklist:token:YOUR_TOKEN_HERE"

# Check application logs
docker logs docker-api-1 --tail 100 | grep blacklist
```

**Common Causes:**
1. Redis connection failure (check `cache.ping()`)
2. Token not being extracted correctly (check Authorization header format)
3. Different token used for logout vs. subsequent requests

**Solution:**
- Verify Redis connectivity: `docker exec docker-redis-1 redis-cli PING`
- Check application logs for errors
- Ensure same token is used for logout and subsequent requests

### Issue: 401 "Token has been revoked" on valid token

**Symptoms:**
- User just logged in
- Immediately gets "Token has been revoked" error

**Diagnosis:**
```bash
# Check if token is blacklisted
docker exec docker-redis-1 redis-cli EXISTS "blacklist:token:YOUR_TOKEN_HERE"
# Output: 1 = blacklisted, 0 = not blacklisted
```

**Common Causes:**
1. Token from previous session still in blacklist
2. Clock skew between servers
3. Accidental logout during development

**Solution:**
- Get new token with fresh login
- Check server time synchronization (NTP)
- Clear Redis blacklist in development: `docker exec docker-redis-1 redis-cli FLUSHDB`

### Issue: Redis connection errors

**Symptoms:**
```
2025-11-20 20:35:22 - services.cache_service - WARNING - Failed to initialize Redis: [Errno 111] Connection refused
```

**Diagnosis:**
```bash
# Check Redis container status
docker ps | grep redis

# Check Redis logs
docker logs docker-redis-1 --tail 50

# Test Redis connectivity
docker exec docker-redis-1 redis-cli PING
```

**Solution:**
1. Start Redis container: `docker-compose -f docker/docker-compose.yaml up -d redis`
2. Check Redis URL in environment: `echo $REDIS_URL`
3. Verify network connectivity between containers

## Future Enhancements

### Phase 2: Session Management (Planned)

1. **Database Schema:**
   - `user_sessions` table with token_hash, device_info, IP address
   - Track all active sessions per user

2. **Endpoints:**
   - `GET /api/v1/sessions` - List current user's sessions
   - `DELETE /api/v1/sessions/{id}` - Revoke specific session
   - `DELETE /api/v1/sessions` - Revoke all sessions except current

3. **Features:**
   - "Logout from all devices" functionality
   - Session activity tracking
   - Device/browser fingerprinting
   - Geographic session analytics

### Refresh Token Blacklist (Recommended)

Currently, refresh tokens are NOT blacklisted on logout. This means:
- User logs out → Access token blacklisted ✅
- User can still get new access token with refresh token ❌

**Implementation:**
```python
@router.post("/logout")
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    refresh_token: Optional[str] = None,  # Add refresh token parameter
    current_user: dict = Depends(get_current_active_user)
):
    # Blacklist access token
    await blacklist_service.blacklist_token(credentials.credentials, "access")
    
    # Blacklist refresh token if provided
    if refresh_token:
        await blacklist_service.blacklist_token(refresh_token, "refresh")
```

### Token Rotation

Implement automatic token rotation on each refresh:
1. Generate new access token AND new refresh token
2. Blacklist old refresh token
3. Return both new tokens to client
4. Mitigates refresh token theft risk

## References

- **JWT Best Practices:** https://datatracker.ietf.org/doc/html/rfc8725
- **Redis Documentation:** https://redis.io/docs/
- **FastAPI Security:** https://fastapi.tiangolo.com/tutorial/security/
- **OAuth 2.0 Token Revocation:** https://datatracker.ietf.org/doc/html/rfc7009

## Changelog

### Version 1.0.0 (2025-11-20)

**Added:**
- Token blacklist service with Redis backend
- Automatic TTL calculation from JWT expiration
- Logout endpoint enhancement to blacklist tokens
- Auth middleware check for blacklisted tokens
- Admin endpoints for blacklist management:
  - GET /auth/blacklist/stats
  - POST /auth/blacklist/remove
  - POST /auth/blacklist/user/{user_id}
- Cache service enhancements:
  - exists() method for blacklist checks
  - ttl() method for remaining TTL
  - keys() method for pattern matching
- Comprehensive logging and error handling
- RBAC enforcement on admin endpoints

**Tested:**
- Complete logout flow (login → use → logout → fail)
- Blacklist persistence in Redis with correct TTL
- Admin stats endpoint functionality
- RBAC enforcement (non-admin gets 403)
- New login after logout works correctly

**Known Limitations:**
- Refresh tokens not blacklisted on logout
- No session tracking (list/revoke all sessions)
- KEYS operation in stats (O(N) - avoid in production)
- No automatic token rotation

---

**Document Version:** 1.0.0  
**Last Updated:** 2025-11-20  
**Author:** GitHub Copilot  
**Status:** Production Ready
