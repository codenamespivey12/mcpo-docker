# Context7 MCP Server Configuration

## Overview

The Context7 MCP server provides up-to-date documentation and code examples for various libraries and frameworks. It allows AI assistants to access current documentation rather than relying on potentially outdated training data.

## Configuration Options

### Basic Configuration

```json
{
  "mcpServers": {
    "context7": {
      "command": "npx",
      "args": ["-y", "@upstash/context7-mcp"],
      "disabled": false,
      "autoApprove": ["resolve-library-id", "get-library-docs"]
    }
  }
}
```

### Configuration Parameters

| Parameter | Type | Description | Required | Default |
|-----------|------|-------------|----------|---------|
| `command` | string | Command to run the MCP server | Yes | `"npx"` |
| `args` | array | Arguments to pass to the command | Yes | `["-y", "@upstash/context7-mcp"]` |
| `disabled` | boolean | Whether the MCP server is disabled | No | `false` |
| `autoApprove` | array | List of tool names to auto-approve | No | `["resolve-library-id", "get-library-docs"]` |
| `env` | object | Environment variables for the MCP server | No | `{}` |
| `timeout` | number | Timeout in seconds for MCP server operations | No | `60` |

### Alternative Configurations

#### Using Bun

```json
{
  "mcpServers": {
    "context7": {
      "command": "bunx",
      "args": ["-y", "@upstash/context7-mcp"],
      "disabled": false,
      "autoApprove": ["resolve-library-id", "get-library-docs"]
    }
  }
}
```

#### Using Deno

```json
{
  "mcpServers": {
    "context7": {
      "command": "deno",
      "args": ["run", "--allow-env=NO_DEPRECATION,TRACE_DEPRECATION", "--allow-net", "npm:@upstash/context7-mcp"],
      "disabled": false,
      "autoApprove": ["resolve-library-id", "get-library-docs"]
    }
  }
}
```

## Available Tools

Context7 MCP provides the following tools:

1. `resolve-library-id`: Resolves a general library name into a Context7-compatible library ID.
   - Parameters:
     - `libraryName` (required): The name of the library to search for

2. `get-library-docs`: Fetches documentation for a library using a Context7-compatible library ID.
   - Parameters:
     - `context7CompatibleLibraryID` (required): Exact Context7-compatible library ID (e.g., `/mongodb/docs`, `/vercel/next.js`)
     - `topic` (optional): Focus the docs on a specific topic (e.g., "routing", "hooks")
     - `tokens` (optional, default 10000): Max number of tokens to return

## Troubleshooting

### Module Not Found Errors

If you encounter `ERR_MODULE_NOT_FOUND`, try using `bunx` instead of `npx`:

```json
{
  "mcpServers": {
    "context7": {
      "command": "bunx",
      "args": ["-y", "@upstash/context7-mcp"],
      "disabled": false,
      "autoApprove": ["resolve-library-id", "get-library-docs"]
    }
  }
}
```

### ESM Resolution Issues

For errors like `Error: Cannot find module 'uriTemplate.js'`, try the `--experimental-vm-modules` flag:

```json
{
  "mcpServers": {
    "context7": {
      "command": "npx",
      "args": ["-y", "--node-options=--experimental-vm-modules", "@upstash/context7-mcp"],
      "disabled": false,
      "autoApprove": ["resolve-library-id", "get-library-docs"]
    }
  }
}
```

### TLS/Certificate Issues

Use the `--experimental-fetch` flag to bypass TLS-related problems:

```json
{
  "mcpServers": {
    "context7": {
      "command": "npx",
      "args": ["-y", "--node-options=--experimental-fetch", "@upstash/context7-mcp"],
      "disabled": false,
      "autoApprove": ["resolve-library-id", "get-library-docs"]
    }
  }
}
```