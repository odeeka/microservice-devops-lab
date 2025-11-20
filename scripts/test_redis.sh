#!/bin/bash
echo "🧪 Testing Redis Cache Implementation"
echo "======================================"
echo ""

echo "1️⃣  Testing Items List Endpoint (Cache MISS)"
curl -s http://localhost/api/v1/items?limit=3 | jq -r '.[].name' | head -2
echo ""

echo "2️⃣  Testing Items List Endpoint (Cache HIT)"
curl -s http://localhost/api/v1/items?limit=3 > /dev/null
echo "✅ Second request completed (should be cached)"
echo ""

echo "3️⃣  Creating new item (Cache Invalidation)"
curl -s -X POST http://localhost/api/v1/items \
  -H "Content-Type: application/json" \
  -d '{"name": "Redis Test Item", "description": "Cache test", "price": 42.00, "category": "Test"}' | jq -r '.name'
echo ""

echo "4️⃣  Testing Statistics Endpoint (Cache MISS)"
curl -s http://localhost/api/v1/items/stats/summary | jq -r '.total_items, .active_items' | head -2
echo ""

echo "5️⃣  Testing Statistics Endpoint (Cache HIT)"
curl -s http://localhost/api/v1/items/stats/summary > /dev/null
echo "✅ Second stats request completed (should be cached)"
echo ""

echo "6️⃣  Checking Redis Keys"
docker exec docker-redis-1 redis-cli KEYS "*"
echo ""

echo "7️⃣  Cache Activity Logs"
docker compose -f docker/docker-compose.yaml logs api 2>&1 | grep -E "Cache|cache" | tail -8
echo ""

echo "✅ Test completed!"
