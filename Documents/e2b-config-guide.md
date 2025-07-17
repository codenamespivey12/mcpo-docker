# E2B MCP Server Configuration Guide

This guide explains how to configure and use the E2B MCP server in the MCP Docker setup.

## Overview

The E2B MCP server provides a secure sandbox environment for running code through the Model Context Protocol. It allows AI assistants to execute code in a secure, isolated environment.

## Configuration Options

### Basic Configuration

The E2B MCP server is configured in the `config.json` file under the `mcpServers` section:

```json
{
  "mcpServers": {
    "e2b": {
      "command": "uvx",
      "args": [
        "e2b-mcp-server"
      ],
      "env": {
        "E2B_API_KEY": "${E2B_API_KEY}"
      },
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

### Configuration Parameters

| Parameter | Description | Required | Default |
|-----------|-------------|----------|---------|
| `command` | Command to run the MCP server | Yes | `uvx` |
| `args` | Arguments to pass to the command | Yes | `["e2b-mcp-server"]` |
| `env` | Environment variables for the MCP server | No | `{}` |
| `disabled` | Whether the MCP server is disabled | No | `false` |
| `autoApprove` | List of tool names to auto-approve | No | `[]` |
| `timeout` | Timeout in seconds for MCP server operations | No | `60` |

### Environment Variables

The E2B MCP server requires the following environment variables:

| Variable | Description | Required |
|----------|-------------|----------|
| `E2B_API_KEY` | API key for E2B service | Yes |

## Docker Deployment

When deploying with Docker, you need to provide the E2B API key as an environment variable:

```yaml
services:
  mcpo:
    image: ghcr.io/alephpiece/mcpo
    ports:
      - "8000:8000"
    volumes:
      - ./config.json:/app/config.json
    environment:
      - E2B_API_KEY=your_api_key_here
```

Alternatively, you can use a `.env` file:

```
E2B_API_KEY=your_api_key_here
```

And reference it in your docker-compose.yml:

```yaml
services:
  mcpo:
    image: ghcr.io/alephpiece/mcpo
    ports:
      - "8000:8000"
    volumes:
      - ./config.json:/app/config.json
    env_file:
      - .env
```

## Security Considerations

- Never commit your E2B API key to version control
- Use environment variables or secure secrets management for API keys
- Consider using Docker secrets for production deployments

## Troubleshooting

### Common Issues

1. **Missing API Key**
   
   Error: `E2B_API_KEY environment variable is not set`
   
   Solution: Ensure the E2B_API_KEY environment variable is set in your environment or Docker configuration.

2. **Invalid API Key**
   
   Error: `Invalid API key provided`
   
   Solution: Verify your E2B API key is correct and has the necessary permissions.

3. **Server Not Starting**
   
   Error: `Failed to start E2B MCP server`
   
   Solution: Check the logs for specific error messages. Ensure the E2B service is available and your API key is valid.

## Additional Resources

- [E2B Documentation](https://e2b.dev/docs)
- [Model Context Protocol Documentation](https://modelcontextprotocol.github.io/)
- [E2B API Reference](https://e2b.dev/docs/api-reference)