# MCP Docker Proxy Server

A Docker-based HTTP gateway for Model Context Protocol (MCP) servers that exposes MCP tools as REST API endpoints.

## Overview

This project creates a unified HTTP interface for multiple MCP servers, allowing you to:

- **Expose MCP servers as HTTP endpoints** - Each server gets its own endpoint (e.g., `/memory`, `/time`, `/exa`)
- **Support multiple server types** - Command-based, SSE, and streamable HTTP MCP servers
- **Call MCP tools via HTTP** - Simple POST requests to call any MCP tool
- **Monitor server health** - Built-in health checks and status monitoring
- **Easy deployment** - Docker and Docker Compose ready

## Quick Start

### Using Docker Compose

1. **Clone and configure:**
   ```bash
   git clone <repository-url>
   cd mcp-docker-proxy
   cp .env.example .env
   # Edit .env with your API keys
   ```

2. **Start the services:**
   ```bash
   docker-compose up -d
   ```

3. **Test the endpoints:**
   ```bash
   # List available servers
   curl http://localhost:8000/
   
   # List tools for memory server
   curl http://localhost:8000/memory
   
   # Call a tool
   curl -X POST http://localhost:8000/memory \
     -H "Content-Type: application/json" \
     -d '{"tool": "create_entities", "arguments": {"entities": [{"name": "Hello_World", "entityType": "greeting", "observations": ["First test entity"]}]}}'
   ```

### Using Docker

```bash
# Build the image
docker build -t mcp-proxy .

# Run with configuration
docker run -p 8000:8000 -v ./config.json:/app/config.json mcp-proxy
```

## Configuration

The server is configured via a JSON file. Here's the structure:

```json
{
  "mcpServers": {
    "memory": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-memory"],
      "disabled": false,
      "autoApprove": []
    },
    "time": {
      "command": "uvx",
      "args": ["mcp-server-time", "--local-timezone=${TIMEZONE}"],
      "env": {
        "FASTMCP_LOG_LEVEL": "ERROR"
      },
      "disabled": false
    },
    "exa": {
      "command": "npx",
      "args": ["-y", "exa-mcp-server"],
      "env": {
        "EXA_API_KEY": "${EXA_API_KEY}"
      },
      "disabled": false,
      "autoApprove": [
        "web_search_exa",
        "research_paper_search_exa"
      ]
    },
    "mcp_sse": {
      "type": "sse",
      "url": "http://127.0.0.1:8001/sse",
      "headers": {
        "Authorization": "Bearer token",
        "X-Custom-Header": "value"
      }
    },
    "mcp_streamable_http": {
      "type": "streamable_http",
      "url": "http://127.0.0.1:8002/mcp",
      "headers": {
        "Authorization": "Bearer token"
      }
    }
  },
  "proxy": {
    "port": 8000,
    "host": "0.0.0.0",
    "logLevel": "info"
  }
}
```

### Server Types

1. **Command-based servers** (default):
   ```json
   {
     "command": "npx",
     "args": ["-y", "@modelcontextprotocol/server-memory"],
     "env": {"API_KEY": "${API_KEY}"},
     "disabled": false
   }
   ```

2. **SSE servers**:
   ```json
   {
     "type": "sse",
     "url": "http://127.0.0.1:8001/sse",
     "headers": {"Authorization": "Bearer token"}
   }
   ```

3. **Streamable HTTP servers**:
   ```json
   {
     "type": "streamable_http",
     "url": "http://127.0.0.1:8002/mcp",
     "headers": {"Authorization": "Bearer token"}
   }
   ```

## API Endpoints

### Server Information
- **GET /** - List available servers and endpoints
- **GET /status** - Detailed server status and health information

### Tool Management
- **GET /{server_name}** - List available tools for a server
- **POST /{server_name}** - Call a tool on a server

### Example Requests

```bash
# List all servers
curl http://localhost:8000/

# Get server status
curl http://localhost:8000/status

# List memory server tools
curl http://localhost:8000/memory

# Create entities in memory
curl -X POST http://localhost:8000/memory \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "create_entities",
    "arguments": {
      "entities": [
        {
          "name": "John_Smith",
          "entityType": "person",
          "observations": ["Works as a software engineer", "Prefers morning meetings"]
        }
      ]
    }
  }'

# Get current time
curl -X POST http://localhost:8000/time \
  -H "Content-Type: application/json" \
  -d '{"tool": "get_current_time", "arguments": {}}'

# Search with Exa
curl -X POST http://localhost:8000/exa \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "web_search_exa",
    "arguments": {
      "query": "latest AI developments",
      "numResults": 5
    }
  }'
```

## Environment Variables

Create a `.env` file with the following variables:

```bash
# Required API keys
E2B_API_KEY=your_e2b_api_key_here
EXA_API_KEY=your_exa_api_key_here

# Configuration
CONFIG_PATH=./config.json
MCP_PORT=8000
TIMEZONE=UTC
LOG_LEVEL=info
LOG_FORMAT=json

# Resource limits
CPU_LIMIT=1
MEMORY_LIMIT=1G
PROCESS_LIMIT=10
```

## Included MCP Servers

The default configuration includes several popular MCP servers:

1. **Memory Server** (`@modelcontextprotocol/server-memory`)
   - Knowledge graph-based persistent memory system
   - Tools: `create_entities`, `create_relations`, `add_observations`, `delete_entities`, `delete_observations`, `delete_relations`, `read_graph`, `search_nodes`, `open_nodes`

2. **Time Server** (`mcp-server-time`)
   - Get current time and date information
   - Tools: `get_current_time`, `get_timezone_info`

3. **Sequential Thinking** (`@modelcontextprotocol/server-sequential-thinking`)
   - Structured thinking and reasoning
   - Tools: `sequential_thinking`

4. **Context7** (`@upstash/context7-mcp`)
   - Library documentation and context
   - Tools: `resolve-library-id`, `get-library-docs`

5. **E2B** (`e2b-mcp-server`)
   - Code execution environment
   - Tools: Various code execution tools

6. **Exa** (`exa-mcp-server`)
   - Web search and research
   - Tools: `web_search_exa`, `research_paper_search_exa`, etc.

## Health Monitoring

The server includes comprehensive health monitoring:

- **Health checks** - Docker health checks and HTTP endpoints
- **Process monitoring** - Automatic restart of failed MCP servers
- **Resource monitoring** - CPU, memory, and disk usage tracking
- **Structured logging** - JSON or text format logging

Access health information:
```bash
# Basic health check
curl http://localhost:8000/status

# Detailed server status
curl http://localhost:8000/status | jq
```

## Development

### Running Locally

```bash
# Install dependencies (if needed)
pip install requests

# Run the proxy server
python3 mcp_proxy.py --config config.example.json

# Run tests
python3 test_mcp_proxy.py --test

# See usage examples
python3 test_mcp_proxy.py --demo
```

### Testing

```bash
# Run the test suite
python3 test_mcp_proxy.py --test

# Test individual components
python3 test_health_check.py
python3 test_config_handler.py
```

### Adding New MCP Servers

1. **Add to configuration:**
   ```json
   {
     "mcpServers": {
       "your_server": {
         "command": "your-command",
         "args": ["--arg1", "--arg2"],
         "env": {"API_KEY": "${YOUR_API_KEY}"},
         "disabled": false
       }
     }
   }
   ```

2. **Restart the service:**
   ```bash
   docker-compose restart
   ```

3. **Test the new endpoint:**
   ```bash
   curl http://localhost:8000/your_server
   ```

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   HTTP Client   │───▶│   MCP Proxy      │───▶│   MCP Server    │
│                 │    │   Server         │    │   (memory)      │
└─────────────────┘    │                  │    └─────────────────┘
                       │  ┌─────────────┐ │    ┌─────────────────┐
                       │  │   Health    │ │───▶│   MCP Server    │
                       │  │   Monitor   │ │    │   (time)        │
                       │  └─────────────┘ │    └─────────────────┘
                       │                  │    ┌─────────────────┐
                       │  ┌─────────────┐ │───▶│   MCP Server    │
                       │  │   Process   │ │    │   (exa)         │
                       │  │   Monitor   │ │    └─────────────────┘
                       └──┴─────────────┴─┘
```

## Troubleshooting

### Common Issues

1. **Server won't start:**
   - Check configuration file syntax
   - Verify API keys are set
   - Check port availability

2. **MCP server not responding:**
   - Check server logs: `docker-compose logs`
   - Verify server dependencies are installed
   - Check environment variables

3. **Tool calls failing:**
   - Verify tool name and arguments
   - Check server-specific documentation
   - Review error messages in logs

### Debugging

```bash
# View logs
docker-compose logs -f

# Check server status
curl http://localhost:8000/status

# Test individual servers
curl http://localhost:8000/memory
curl http://localhost:8000/time
```
