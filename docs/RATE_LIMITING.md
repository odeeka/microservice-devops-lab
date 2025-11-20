# Redis-Based Rate Limiting Implementation

## ✅ Successfully Implemented

### Overview

**IP-based rate limiting** has been implemented using Redis to protect the API from abuse and ensure fair resource usage across all clients.

## 🎯 Features

### 1. **IP-Based Rate Limiting**
- Tracks requests per IP address
- Configurable limit per minute
- Automatic blocking after exceeding limit
- TTL-based expiration (sliding window)

### 2. **Request Tracking**
```
rate_limit:<ip_address> = request_count
```
- Increments on each request
- Expires after 60 seconds
- Example: `rate_limit:192.168.1.100 = 45`

### 3. **IP Blocking**
```
rate_limit:blocked:<ip_address> = "blocked"
```
- Created when limit exceeded
- Blocks all requests during block period
- Example: After 11th request, IP blocked for 60 seconds

### 4. **Response Headers**
Every response includes rate limit information:
```http
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 7
X-RateLimit-Reset: 60
```

### 5. **Graceful Degradation**
- If Redis unavailable → Rate limiting disabled
- Application continues normally
- Logged as warning

## 📝 Configuration

### Environment Variables (.env)

```bash
# Rate Limiting Configuration
RATE_LIMIT_ENABLED=true                    # Enable/disable rate limiting
RATE_LIMIT_REQUESTS_PER_MINUTE=10          # Max requests per IP per minute
RATE_LIMIT_BLOCK_DURATION=60               # Block duration in seconds
```

### Examples

**Lenient (Development)**:
```bash
RATE_LIMIT_REQUESTS_PER_MINUTE=100
RATE_LIMIT_BLOCK_DURATION=30
```

**Strict (Production)**:
```bash
RATE_LIMIT_REQUESTS_PER_MINUTE=20
RATE_LIMIT_BLOCK_DURATION=300  # 5 minutes
```

**Very Strict (Public API)**:
```bash
RATE_LIMIT_REQUESTS_PER_MINUTE=10
RATE_LIMIT_BLOCK_DURATION=600  # 10 minutes
```

## 🚦 How It Works

### Request Flow

```
1. Request arrives → Extract Client IP
2. Check if IP is blocked
   ├─ YES → Return HTTP 429 with retry-after header
   └─ NO → Continue to step 3
3. Increment request counter for IP
4. Check if limit exceeded
   ├─ YES → Block IP, return HTTP 429
   └─ NO → Process request normally
5. Add rate limit headers to response
```

### Example Scenario

**Configuration**: 10 requests/minute, 60s block

```
Request 1-10: ✅ HTTP 200 OK
Request 11: ⛔ HTTP 429 Too Many Requests (IP blocked for 60s)
Request 12-N (within 60s): ⛔ HTTP 429 (still blocked)
After 60s: ✅ Counter resets, requests allowed again
```

## 🔍 Excluded Paths

These paths bypass rate limiting:
- `/health` - Health check endpoint
- `/metrics` - Prometheus metrics
- `/docs` - Swagger documentation
- `/redoc` - ReDoc documentation  
- `/openapi.json` - OpenAPI schema

## 📊 Redis Keys

### Rate Limit Counter
```
Key: rate_limit:<ip_address>
Value: <request_count>
TTL: 60 seconds
Example: rate_limit:192.168.1.100 = 8
```

### Blocked IP
```
Key: rate_limit:blocked:<ip_address>
Value: "blocked"
TTL: <RATE_LIMIT_BLOCK_DURATION> seconds
Example: rate_limit:blocked:192.168.1.100 = "blocked"
```

## 🧪 Testing

### Test 1: Normal Usage

```bash
# Make 5 requests (should all succeed)
for i in {1..5}; do
  curl -v http://localhost/api/v1/items?limit=1
  echo "Request $i done"
done
```

**Expected**: All return HTTP 200

### Test 2: Exceed Limit

```bash
# Make 12 requests (limit is 10)
for i in {1..12}; do
  status=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/api/v1/items?limit=1)
  echo "Request $i: HTTP $status"
done
```

**Expected**:
```
Request 1-10: HTTP 200
Request 11-12: HTTP 429
```

### Test 3: Check Headers

```bash
curl -I http://localhost/api/v1/items?limit=1
```

**Expected Headers**:
```
HTTP/1.1 200 OK
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 9
X-RateLimit-Reset: 60
```

### Test 4: Check Block Duration

```bash
# Trigger block
for i in {1..11}; do curl -s http://localhost/api/v1/items > /dev/null; done

# Check TTL
docker exec docker-redis-1 redis-cli TTL "rate_limit:blocked:172.18.0.1"
```

**Expected**: Returns remaining seconds (e.g., 58, 57, 56...)

### Test 5: Monitor in Real-Time

```bash
# Terminal 1: Watch logs
docker compose -f docker/docker-compose.yaml logs -f api | grep "Rate limit"

# Terminal 2: Make requests
for i in {1..15}; do curl http://localhost/api/v1/items?limit=1; done
```

### Test 6: Inspect Redis

```bash
# View all rate limit keys
docker exec docker-redis-1 redis-cli KEYS "rate_limit:*"

# Get specific counter
docker exec docker-redis-1 redis-cli GET "rate_limit:172.18.0.1"

# Check if IP is blocked
docker exec docker-redis-1 redis-cli EXISTS "rate_limit:blocked:172.18.0.1"
```

## 📋 Log Messages

### Normal Request
```
🚦 Rate limit: 172.18.0.1 - 10/10 requests - 0 remaining
```

### Limit Exceeded (First Time)
```
⛔ Rate limit EXCEEDED: 172.18.0.1 - 11 requests in 60s - BLOCKING for 60s
🚫 IP 172.18.0.1 blocked for 60 seconds
```

### Subsequent Blocked Requests
```
⛔ Rate limit BLOCKED: 172.18.0.1 - Blocked for 45s more
```

## 🌐 Response Format

### HTTP 429 - Rate Limit Exceeded

```json
{
  "error": "Rate limit exceeded",
  "message": "You made 11 requests in 1 minute. Limit is 10. Blocked for 60 seconds.",
  "retry_after": 60
}
```

**Headers**:
```
HTTP/1.1 429 Too Many Requests
Retry-After: 60
Content-Type: application/json
```

## 🛡️ Security Considerations

### 1. **IP Extraction**

The middleware checks headers in this order:
1. `X-Forwarded-For` (first IP in chain)
2. `X-Real-IP`
3. Direct client IP

**Behind NGINX/Proxy**:
```nginx
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
```

### 2. **Distributed Environments**

- Redis ensures consistent rate limiting across multiple API instances
- All instances share the same rate limit counters
- No need for sticky sessions

### 3. **Bot Protection**

Rate limiting helps protect against:
- ✅ Brute force attacks
- ✅ API scraping
- ✅ DDoS attempts
- ✅ Resource exhaustion

## 🔧 Advanced Usage

### Per-Endpoint Rate Limiting

Use `RateLimiter` class for specific endpoints:

```python
from middleware.rate_limit import RateLimiter

rate_limiter = RateLimiter()

@router.post("/expensive-operation")
async def expensive_operation(request: Request):
    # Limit this endpoint to 5 requests per minute
    await rate_limiter.check_rate_limit(
        request, 
        limit=5,
        window=60,
        key_prefix="endpoint:expensive"
    )
    # ... process request
```

### Custom Limits by User/API Key

```python
# Get user tier from database/JWT
user_tier = get_user_tier(request)

limits = {
    "free": 10,
    "premium": 100,
    "enterprise": 1000
}

await rate_limiter.check_rate_limit(
    request,
    limit=limits[user_tier],
    key_prefix=f"user:{user_id}"
)
```

## 📈 Monitoring

### Prometheus Metrics (Future Enhancement)

```python
# Add to middleware
rate_limit_requests = Counter(
    "rate_limit_requests_total",
    "Total requests checked by rate limiter",
    ["ip", "blocked"]
)

rate_limit_blocks = Counter(
    "rate_limit_blocks_total",
    "Total IPs blocked by rate limiter",
    ["ip"]
)
```

### Grafana Dashboard

Track:
- Requests per IP over time
- Number of blocked IPs
- Top offending IPs
- Rate limit hit ratio

## 🚀 Performance

### Redis Operation Cost

- **GET** (check block): ~0.1ms
- **INCR** (increment counter): ~0.1ms
- **SETEX** (block IP): ~0.1ms

**Total overhead per request**: ~0.3ms (negligible)

### Memory Usage

Per IP:
- Counter: ~50 bytes
- Block key: ~50 bytes

**Example**: 1000 unique IPs = ~100KB memory

## 🔄 Comparison with NGINX Rate Limiting

| Feature | NGINX | Redis (Application) |
|---------|-------|---------------------|
| Scope | Per NGINX instance | Global across all instances |
| Flexibility | Limited | Highly customizable |
| Per-endpoint limits | Complex | Easy |
| User-based limits | Not possible | Easy |
| Dynamic configuration | Restart required | Hot reload via config |
| Granular logging | Limited | Detailed |
| Custom logic | Not possible | Full control |

**Recommendation**: Use both for defense in depth!

## 📚 Files Modified/Created

- ✅ **Created**: `app/middleware/rate_limit.py` - Rate limiting middleware
- ✅ **Created**: `app/middleware/__init__.py` - Module init
- ✅ **Modified**: `app/main.py` - Added middleware registration
- ✅ **Modified**: `app/config.py` - Added rate limit configuration
- ✅ **Modified**: `.env` - Added rate limit environment variables

## 🐛 Troubleshooting

### Rate limiting not working

**Check Redis connection**:
```bash
docker exec docker-api-1 env | grep REDIS
docker exec docker-redis-1 redis-cli PING
```

**Check if enabled**:
```bash
docker exec docker-api-1 env | grep RATE_LIMIT
docker compose -f docker/docker-compose.yaml logs api | grep "Rate limiting"
```

### All requests blocked immediately

**Clear Redis keys**:
```bash
docker exec docker-redis-1 redis-cli DEL "rate_limit:blocked:YOUR_IP"
docker exec docker-redis-1 redis-cli DEL "rate_limit:YOUR_IP"
```

### Rate limit too strict

**Increase limit temporarily**:
```bash
# Edit .env
RATE_LIMIT_REQUESTS_PER_MINUTE=100

# Restart
docker compose -f docker/docker-compose.yaml restart api
```

## ✅ Summary

Redis-based IP rate limiting is now fully implemented with:

- ✅ **Configurable limits** via environment variables
- ✅ **Automatic IP blocking** after exceeding limit
- ✅ **TTL-based expiration** (sliding window)
- ✅ **Rate limit headers** in all responses
- ✅ **Detailed logging** of all rate limit events
- ✅ **Graceful degradation** if Redis unavailable
- ✅ **Excluded paths** for health checks and docs
- ✅ **Production-ready** error handling

**Example Configuration**:
```
Rate Limit: 10 requests/minute per IP
Block Duration: 60 seconds
Status: ✅ Active
```

The system protects your API from abuse while maintaining excellent performance!
