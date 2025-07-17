#!/usr/bin/env python3
"""
Test script for the MCP Proxy Server.
Demonstrates how to interact with different types of MCP servers through HTTP endpoints.
"""

import json
import time
import requests
import subprocess
import threading
from typing import Dict, Any

# Test configuration with different server types
TEST_CONFIG = {
    "mcpServers": {
        "memory": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-memory"],
            "disabled": False,
            "autoApprove": []
        },
        "time": {
            "command": "uvx",
            "args": ["mcp-server-time", "--local-timezone=America/New_York"],
            "env": {
                "FASTMCP_LOG_LEVEL": "ERROR"
            },
            "disabled": False,
            "autoApprove": []
        },
        "mcp_sse": {
            "type": "sse",
            "url": "http://127.0.0.1:8001/sse",
            "headers": {
                "Authorization": "Bearer token",
                "X-Custom-Header": "value"
            },
            "disabled": True  # Disabled for testing since we don't have a real SSE server
        },
        "mcp_streamable_http": {
            "type": "streamable_http",
            "url": "http://127.0.0.1:8002/mcp",
            "headers": {
                "Authorization": "Bearer token"
            },
            "disabled": True  # Disabled for testing since we don't have a real HTTP server
        }
    },
    "proxy": {
        "port": 8000,
        "host": "0.0.0.0",
        "logLevel": "info"
    }
}


def test_proxy_endpoints():
    """
    Test the MCP proxy server endpoints.
    """
    base_url = "http://localhost:8000"
    
    print("🧪 Testing MCP Proxy Server Endpoints")
    print("=" * 50)
    
    # Test 1: Get server information
    print("\n1. Testing server information endpoint (GET /)")
    try:
        response = requests.get(f"{base_url}/")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Server info: {json.dumps(data, indent=2)}")
        else:
            print(f"❌ Failed to get server info: {response.status_code}")
    except Exception as e:
        print(f"❌ Error getting server info: {str(e)}")
    
    # Test 2: Get server status
    print("\n2. Testing server status endpoint (GET /status)")
    try:
        response = requests.get(f"{base_url}/status")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Server status: {json.dumps(data, indent=2)}")
        else:
            print(f"❌ Failed to get server status: {response.status_code}")
    except Exception as e:
        print(f"❌ Error getting server status: {str(e)}")
    
    # Test 3: List tools for memory server
    print("\n3. Testing tools listing for memory server (GET /memory)")
    try:
        response = requests.get(f"{base_url}/memory")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Memory server tools: {json.dumps(data, indent=2)}")
        else:
            print(f"❌ Failed to list memory tools: {response.status_code}")
    except Exception as e:
        print(f"❌ Error listing memory tools: {str(e)}")
    
    # Test 4: List tools for time server
    print("\n4. Testing tools listing for time server (GET /time)")
    try:
        response = requests.get(f"{base_url}/time")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Time server tools: {json.dumps(data, indent=2)}")
        else:
            print(f"❌ Failed to list time tools: {response.status_code}")
    except Exception as e:
        print(f"❌ Error listing time tools: {str(e)}")
    
    # Test 5: Call a tool on the memory server
    print("\n5. Testing tool call on memory server (POST /memory)")
    try:
        # Example: Store a memory
        payload = {
            "tool": "store_memory",
            "arguments": {
                "content": "This is a test memory stored via HTTP API",
                "metadata": {
                    "source": "test_script",
                    "timestamp": time.time()
                }
            }
        }
        
        response = requests.post(
            f"{base_url}/memory",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Memory tool call result: {json.dumps(data, indent=2)}")
        else:
            print(f"❌ Failed to call memory tool: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Error calling memory tool: {str(e)}")
    
    # Test 6: Call a tool on the time server
    print("\n6. Testing tool call on time server (POST /time)")
    try:
        # Example: Get current time
        payload = {
            "tool": "get_current_time",
            "arguments": {}
        }
        
        response = requests.post(
            f"{base_url}/time",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Time tool call result: {json.dumps(data, indent=2)}")
        else:
            print(f"❌ Failed to call time tool: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Error calling time tool: {str(e)}")
    
    # Test 7: Test error handling - non-existent server
    print("\n7. Testing error handling - non-existent server (GET /nonexistent)")
    try:
        response = requests.get(f"{base_url}/nonexistent")
        if response.status_code == 404:
            data = response.json()
            print(f"✅ Proper error handling: {json.dumps(data, indent=2)}")
        else:
            print(f"❌ Unexpected response for non-existent server: {response.status_code}")
    except Exception as e:
        print(f"❌ Error testing non-existent server: {str(e)}")
    
    # Test 8: Test error handling - invalid tool call
    print("\n8. Testing error handling - invalid tool call (POST /memory)")
    try:
        payload = {
            "tool": "nonexistent_tool",
            "arguments": {}
        }
        
        response = requests.post(
            f"{base_url}/memory",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code >= 400:
            data = response.json()
            print(f"✅ Proper error handling for invalid tool: {json.dumps(data, indent=2)}")
        else:
            print(f"❌ Unexpected success for invalid tool call: {response.status_code}")
    except Exception as e:
        print(f"❌ Error testing invalid tool call: {str(e)}")


def create_test_config():
    """
    Create a test configuration file.
    """
    with open("test_config.json", "w") as f:
        json.dump(TEST_CONFIG, f, indent=2)
    print("📝 Created test_config.json")


def run_proxy_server():
    """
    Run the MCP proxy server for testing.
    """
    print("🚀 Starting MCP proxy server for testing...")
    
    # Create test config
    create_test_config()
    
    # Start the proxy server
    process = subprocess.Popen([
        "python3", "mcp_proxy.py",
        "--config", "test_config.json",
        "--host", "localhost",
        "--port", "8000"
    ])
    
    # Wait a bit for the server to start
    time.sleep(5)
    
    try:
        # Run tests
        test_proxy_endpoints()
    finally:
        # Stop the server
        print("\n🛑 Stopping MCP proxy server...")
        process.terminate()
        process.wait()


def demonstrate_usage():
    """
    Demonstrate how to use the MCP proxy server.
    """
    print("📚 MCP Proxy Server Usage Examples")
    print("=" * 50)
    
    print("""
The MCP Proxy Server exposes each configured MCP server as HTTP endpoints:

1. **Server Information** (GET /)
   - Returns list of available servers and endpoints
   
2. **Server Status** (GET /status)
   - Returns detailed status of all MCP servers
   
3. **List Tools** (GET /{server_name})
   - Lists available tools for a specific server
   - Example: GET /memory, GET /time, GET /exa
   
4. **Call Tools** (POST /{server_name})
   - Calls a specific tool on a server
   - Request body: {"tool": "tool_name", "arguments": {...}}
   - Example: POST /memory with {"tool": "store_memory", "arguments": {...}}

**Configuration Examples:**

Command-based MCP server:
```json
{
  "memory": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-memory"],
    "disabled": false
  }
}
```

SSE-based MCP server:
```json
{
  "mcp_sse": {
    "type": "sse",
    "url": "http://127.0.0.1:8001/sse",
    "headers": {
      "Authorization": "Bearer token"
    }
  }
}
```

Streamable HTTP MCP server:
```json
{
  "mcp_streamable_http": {
    "type": "streamable_http",
    "url": "http://127.0.0.1:8002/mcp"
  }
}
```

**Usage with curl:**

# List available servers
curl http://localhost:8000/

# Get server status
curl http://localhost:8000/status

# List tools for memory server
curl http://localhost:8000/memory

# Call a tool on memory server
curl -X POST http://localhost:8000/memory \\
  -H "Content-Type: application/json" \\
  -d '{"tool": "store_memory", "arguments": {"content": "Hello World"}}'

# Call a tool on time server
curl -X POST http://localhost:8000/time \\
  -H "Content-Type: application/json" \\
  -d '{"tool": "get_current_time", "arguments": {}}'
""")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        demonstrate_usage()
    elif len(sys.argv) > 1 and sys.argv[1] == "--test":
        run_proxy_server()
    else:
        print("Usage:")
        print("  python3 test_mcp_proxy.py --demo   # Show usage examples")
        print("  python3 test_mcp_proxy.py --test   # Run integration tests")