#!/bin/bash

# Test script for Railway deployment
# Usage: ./test-railway.sh https://your-app-name.railway.app

if [ -z "$1" ]; then
    echo "Usage: $0 <railway-app-url>"
    echo "Example: $0 https://your-app-name.railway.app"
    exit 1
fi

APP_URL="$1"
echo "🧪 Testing MCP Proxy deployment at: $APP_URL"
echo "=" * 50

# Test 1: Server info
echo -e "\n1. Testing server info (GET /)..."
curl -s "$APP_URL/" | jq '.' || echo "❌ Failed to get server info"

# Test 2: Server status
echo -e "\n2. Testing server status (GET /status)..."
curl -s "$APP_URL/status" | jq '.memory' || echo "❌ Failed to get server status"

# Test 3: Memory server tools
echo -e "\n3. Testing memory server tools (GET /memory)..."
curl -s "$APP_URL/memory" | jq '.tools[0:3]' || echo "❌ Failed to list memory tools"

# Test 4: Time server tools
echo -e "\n4. Testing time server tools (GET /time)..."
curl -s "$APP_URL/time" | jq '.tools[0:2]' || echo "❌ Failed to list time tools"

# Test 5: Create entity in memory
echo -e "\n5. Testing memory tool call (POST /memory)..."
curl -s -X POST "$APP_URL/memory" \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "create_entities",
    "arguments": {
      "entities": [
        {
          "name": "Railway_Test",
          "entityType": "deployment",
          "observations": ["Deployed successfully on Railway", "Test completed at '$(date)'"]
        }
      ]
    }
  }' | jq '.' || echo "❌ Failed to create entity"

# Test 6: Get current time
echo -e "\n6. Testing time tool call (POST /time)..."
curl -s -X POST "$APP_URL/time" \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "get_current_time",
    "arguments": {}
  }' | jq '.' || echo "❌ Failed to get current time"

# Test 7: Read memory graph
echo -e "\n7. Testing memory graph read (POST /memory)..."
curl -s -X POST "$APP_URL/memory" \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "read_graph",
    "arguments": {}
  }' | jq '.result.entities | length' || echo "❌ Failed to read memory graph"

echo -e "\n✅ Testing complete!"
echo "If all tests passed, your Railway deployment is working correctly!"