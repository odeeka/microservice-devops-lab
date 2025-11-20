#!/bin/bash
echo "🚦 Testing Rate Limiting Implementation"
echo "========================================"
echo "Configuration: 10 requests/minute per IP"
echo "Penalty: Blocked for 60 seconds after exceeding"
echo ""

echo "📊 Making 12 requests rapidly (should trigger rate limit)..."
echo ""

for i in {1..12}; do
    echo -n "Request $i: "
    response=$(curl -s -w "\nHTTP_STATUS:%{http_code}" http://localhost/api/v1/items?limit=1 2>&1)
    status=$(echo "$response" | grep HTTP_STATUS | cut -d: -f2)
    
    if [ "$status" == "429" ]; then
        echo "⛔ BLOCKED (HTTP 429 - Rate Limit Exceeded)"
        # Show the error message
        echo "$response" | grep -v HTTP_STATUS | jq -r '.detail.message' 2>/dev/null || echo "Rate limit exceeded"
    elif [ "$status" == "200" ]; then
        echo "✅ OK (HTTP 200)"
    else
        echo "❓ Status: $status"
    fi
    
    sleep 0.5  # Small delay between requests
done

echo ""
echo "📋 Rate Limiting Logs:"
docker compose -f docker/docker-compose.yaml logs api 2>&1 | grep -E "Rate limit|BLOCKED" | tail -10

echo ""
echo "🔍 Redis Rate Limit Keys:"
docker exec docker-redis-1 redis-cli KEYS "rate_limit:*" 2>/dev/null | head -5

