#!/usr/bin/env python3
"""
MCP Proxy Server - HTTP Gateway for Model Context Protocol servers.

This server creates HTTP endpoints for each configured MCP server, allowing
them to be called like REST APIs. It handles different types of MCP servers:
- Command-based MCP servers (subprocess communication)
- SSE-based MCP servers (Server-Sent Events)
- Streamable HTTP MCP servers

Each MCP server gets its own endpoint (e.g., /memory, /time, /exa) where
tools can be called via HTTP POST requests.
"""

import os
import sys
import json
import time
import signal
import logging
import argparse
import asyncio
import subprocess
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
import threading
from urllib.parse import urlparse

# HTTP server imports
from http.server import HTTPServer, BaseHTTPRequestHandler
import socketserver
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# Configure structured logging
LOG_FORMAT = os.environ.get("LOG_FORMAT", "json").lower()

if LOG_FORMAT == "json":
    import json
    
    class JsonFormatter(logging.Formatter):
        """JSON formatter for structured logging."""
        
        def format(self, record):
            log_record = {
                "timestamp": self.formatTime(record, self.datefmt),
                "level": record.levelname,
                "name": record.name,
                "message": record.getMessage(),
            }
            
            if hasattr(record, "server_name"):
                log_record["server_name"] = record.server_name
                
            if hasattr(record, "request_id"):
                log_record["request_id"] = record.request_id
                
            if record.exc_info:
                log_record["exception"] = self.formatException(record.exc_info)
                
            return json.dumps(log_record)
    
    formatter = JsonFormatter()
else:
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Configure logging handler
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(formatter)

# Configure root logger
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    handlers=[handler]
)

logger = logging.getLogger("mcp_proxy")

# Default configuration
DEFAULT_CONFIG_PATH = os.environ.get("CONFIG_PATH", "/app/config.json")
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = int(os.environ.get("PORT", 8000))


class MCPServerManager:
    """
    Manages MCP server processes and communication.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the MCP server manager.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.servers = {}  # server_name -> server_info
        self.processes = {}  # server_name -> process
        
    def start_servers(self):
        """
        Start all configured MCP servers.
        """
        mcp_servers = self.config.get("mcpServers", {})
        
        for server_name, server_config in mcp_servers.items():
            if server_config.get("disabled", False):
                logger.info(f"Skipping disabled server: {server_name}")
                continue
                
            try:
                self._start_server(server_name, server_config)
            except Exception as e:
                logger.error(f"Failed to start server {server_name}: {str(e)}")
                
    def _start_server(self, server_name: str, server_config: Dict[str, Any]):
        """
        Start a single MCP server.
        
        Args:
            server_name: Name of the server
            server_config: Server configuration
        """
        server_type = server_config.get("type", "command")
        
        if server_type == "command":
            self._start_command_server(server_name, server_config)
        elif server_type == "sse":
            self._start_sse_server(server_name, server_config)
        elif server_type == "streamable_http":
            self._start_http_server(server_name, server_config)
        else:
            logger.error(f"Unknown server type '{server_type}' for server {server_name}")
            
    def _start_command_server(self, server_name: str, server_config: Dict[str, Any]):
        """
        Start a command-based MCP server.
        
        Args:
            server_name: Name of the server
            server_config: Server configuration
        """
        command = server_config.get("command")
        args = server_config.get("args", [])
        env_vars = server_config.get("env", {})
        
        if not command:
            raise ValueError(f"No command specified for server: {server_name}")
            
        # Prepare environment variables
        env = os.environ.copy()
        for key, value in env_vars.items():
            # Handle environment variable substitution
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                env_var_name = value[2:-1]
                if env_var_name in os.environ:
                    env[key] = os.environ[env_var_name]
                else:
                    logger.warning(f"Environment variable not found: {env_var_name}")
                    env[key] = value
            else:
                env[key] = str(value)
        
        # Start the process
        cmd = [command] + args
        logger.info(f"Starting command server: {server_name} - {' '.join(cmd)}")
        
        process = subprocess.Popen(
            cmd,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=0  # Unbuffered
        )
        
        # Store server info
        self.servers[server_name] = {
            "type": "command",
            "config": server_config,
            "process": process,
            "start_time": time.time()
        }
        
        self.processes[server_name] = process
        logger.info(f"Command server started: {server_name} (PID: {process.pid})")
        
    def _start_sse_server(self, server_name: str, server_config: Dict[str, Any]):
        """
        Start an SSE-based MCP server.
        
        Args:
            server_name: Name of the server
            server_config: Server configuration
        """
        url = server_config.get("url")
        headers = server_config.get("headers", {})
        
        if not url:
            raise ValueError(f"No URL specified for SSE server: {server_name}")
            
        logger.info(f"Registering SSE server: {server_name} - {url}")
        
        # Store server info
        self.servers[server_name] = {
            "type": "sse",
            "config": server_config,
            "url": url,
            "headers": headers,
            "start_time": time.time()
        }
        
        logger.info(f"SSE server registered: {server_name}")
        
    def _start_http_server(self, server_name: str, server_config: Dict[str, Any]):
        """
        Start a streamable HTTP MCP server.
        
        Args:
            server_name: Name of the server
            server_config: Server configuration
        """
        url = server_config.get("url")
        headers = server_config.get("headers", {})
        
        if not url:
            raise ValueError(f"No URL specified for HTTP server: {server_name}")
            
        logger.info(f"Registering HTTP server: {server_name} - {url}")
        
        # Store server info
        self.servers[server_name] = {
            "type": "streamable_http",
            "config": server_config,
            "url": url,
            "headers": headers,
            "start_time": time.time()
        }
        
        logger.info(f"HTTP server registered: {server_name}")
        
    def call_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call a tool on the specified MCP server.
        
        Args:
            server_name: Name of the server
            tool_name: Name of the tool to call
            arguments: Tool arguments
            
        Returns:
            Tool response
        """
        if server_name not in self.servers:
            raise ValueError(f"Server not found: {server_name}")
            
        server_info = self.servers[server_name]
        server_type = server_info["type"]
        
        if server_type == "command":
            return self._call_command_tool(server_name, tool_name, arguments)
        elif server_type == "sse":
            return self._call_sse_tool(server_name, tool_name, arguments)
        elif server_type == "streamable_http":
            return self._call_http_tool(server_name, tool_name, arguments)
        else:
            raise ValueError(f"Unknown server type: {server_type}")
            
    def _call_command_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call a tool on a command-based MCP server.
        
        Args:
            server_name: Name of the server
            tool_name: Name of the tool to call
            arguments: Tool arguments
            
        Returns:
            Tool response
        """
        server_info = self.servers[server_name]
        process = server_info["process"]
        
        # Create MCP request
        request = {
            "jsonrpc": "2.0",
            "id": f"{server_name}_{tool_name}_{int(time.time() * 1000)}",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }
        
        try:
            # Send request to process
            request_json = json.dumps(request) + "\n"
            process.stdin.write(request_json)
            process.stdin.flush()
            
            # Read response from process
            response_line = process.stdout.readline()
            if not response_line:
                raise Exception("No response from MCP server")
                
            response = json.loads(response_line.strip())
            
            # Check for errors
            if "error" in response:
                raise Exception(f"MCP server error: {response['error']}")
                
            return response.get("result", {})
            
        except Exception as e:
            logger.error(f"Error calling tool {tool_name} on server {server_name}: {str(e)}")
            raise
            
    def _call_sse_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call a tool on an SSE-based MCP server.
        
        Args:
            server_name: Name of the server
            tool_name: Name of the tool to call
            arguments: Tool arguments
            
        Returns:
            Tool response
        """
        server_info = self.servers[server_name]
        url = server_info["url"]
        headers = server_info["headers"]
        
        # Create MCP request
        request = {
            "jsonrpc": "2.0",
            "id": f"{server_name}_{tool_name}_{int(time.time() * 1000)}",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }
        
        try:
            # Send request to SSE endpoint
            req_headers = headers.copy()
            req_headers["Content-Type"] = "application/json"
            
            req = Request(
                url,
                data=json.dumps(request).encode('utf-8'),
                headers=req_headers,
                method="POST"
            )
            
            with urlopen(req, timeout=30) as response:
                response_data = response.read().decode('utf-8')
                response_json = json.loads(response_data)
                
                # Check for errors
                if "error" in response_json:
                    raise Exception(f"MCP server error: {response_json['error']}")
                    
                return response_json.get("result", {})
                
        except Exception as e:
            logger.error(f"Error calling tool {tool_name} on SSE server {server_name}: {str(e)}")
            raise
            
    def _call_http_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call a tool on a streamable HTTP MCP server.
        
        Args:
            server_name: Name of the server
            tool_name: Name of the tool to call
            arguments: Tool arguments
            
        Returns:
            Tool response
        """
        server_info = self.servers[server_name]
        url = server_info["url"]
        headers = server_info["headers"]
        
        # Create MCP request
        request = {
            "jsonrpc": "2.0",
            "id": f"{server_name}_{tool_name}_{int(time.time() * 1000)}",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }
        
        try:
            # Send request to HTTP endpoint
            req_headers = headers.copy()
            req_headers["Content-Type"] = "application/json"
            
            req = Request(
                url,
                data=json.dumps(request).encode('utf-8'),
                headers=req_headers,
                method="POST"
            )
            
            with urlopen(req, timeout=30) as response:
                response_data = response.read().decode('utf-8')
                response_json = json.loads(response_data)
                
                # Check for errors
                if "error" in response_json:
                    raise Exception(f"MCP server error: {response_json['error']}")
                    
                return response_json.get("result", {})
                
        except Exception as e:
            logger.error(f"Error calling tool {tool_name} on HTTP server {server_name}: {str(e)}")
            raise
            
    def list_tools(self, server_name: str) -> List[Dict[str, Any]]:
        """
        List available tools for the specified MCP server.
        
        Args:
            server_name: Name of the server
            
        Returns:
            List of available tools
        """
        if server_name not in self.servers:
            raise ValueError(f"Server not found: {server_name}")
            
        server_info = self.servers[server_name]
        server_type = server_info["type"]
        
        if server_type == "command":
            return self._list_command_tools(server_name)
        elif server_type == "sse":
            return self._list_sse_tools(server_name)
        elif server_type == "streamable_http":
            return self._list_http_tools(server_name)
        else:
            raise ValueError(f"Unknown server type: {server_type}")
            
    def _list_command_tools(self, server_name: str) -> List[Dict[str, Any]]:
        """
        List tools for a command-based MCP server.
        
        Args:
            server_name: Name of the server
            
        Returns:
            List of available tools
        """
        server_info = self.servers[server_name]
        process = server_info["process"]
        
        # Create MCP request
        request = {
            "jsonrpc": "2.0",
            "id": f"{server_name}_list_tools_{int(time.time() * 1000)}",
            "method": "tools/list"
        }
        
        try:
            # Send request to process
            request_json = json.dumps(request) + "\n"
            process.stdin.write(request_json)
            process.stdin.flush()
            
            # Read response from process
            response_line = process.stdout.readline()
            if not response_line:
                raise Exception("No response from MCP server")
                
            response = json.loads(response_line.strip())
            
            # Check for errors
            if "error" in response:
                raise Exception(f"MCP server error: {response['error']}")
                
            return response.get("result", {}).get("tools", [])
            
        except Exception as e:
            logger.error(f"Error listing tools for server {server_name}: {str(e)}")
            return []
            
    def _list_sse_tools(self, server_name: str) -> List[Dict[str, Any]]:
        """
        List tools for an SSE-based MCP server.
        
        Args:
            server_name: Name of the server
            
        Returns:
            List of available tools
        """
        server_info = self.servers[server_name]
        url = server_info["url"]
        headers = server_info["headers"]
        
        # Create MCP request
        request = {
            "jsonrpc": "2.0",
            "id": f"{server_name}_list_tools_{int(time.time() * 1000)}",
            "method": "tools/list"
        }
        
        try:
            # Send request to SSE endpoint
            req_headers = headers.copy()
            req_headers["Content-Type"] = "application/json"
            
            req = Request(
                url,
                data=json.dumps(request).encode('utf-8'),
                headers=req_headers,
                method="POST"
            )
            
            with urlopen(req, timeout=30) as response:
                response_data = response.read().decode('utf-8')
                response_json = json.loads(response_data)
                
                # Check for errors
                if "error" in response_json:
                    raise Exception(f"MCP server error: {response_json['error']}")
                    
                return response_json.get("result", {}).get("tools", [])
                
        except Exception as e:
            logger.error(f"Error listing tools for SSE server {server_name}: {str(e)}")
            return []
            
    def _list_http_tools(self, server_name: str) -> List[Dict[str, Any]]:
        """
        List tools for a streamable HTTP MCP server.
        
        Args:
            server_name: Name of the server
            
        Returns:
            List of available tools
        """
        server_info = self.servers[server_name]
        url = server_info["url"]
        headers = server_info["headers"]
        
        # Create MCP request
        request = {
            "jsonrpc": "2.0",
            "id": f"{server_name}_list_tools_{int(time.time() * 1000)}",
            "method": "tools/list"
        }
        
        try:
            # Send request to HTTP endpoint
            req_headers = headers.copy()
            req_headers["Content-Type"] = "application/json"
            
            req = Request(
                url,
                data=json.dumps(request).encode('utf-8'),
                headers=req_headers,
                method="POST"
            )
            
            with urlopen(req, timeout=30) as response:
                response_data = response.read().decode('utf-8')
                response_json = json.loads(response_data)
                
                # Check for errors
                if "error" in response_json:
                    raise Exception(f"MCP server error: {response_json['error']}")
                    
                return response_json.get("result", {}).get("tools", [])
                
        except Exception as e:
            logger.error(f"Error listing tools for HTTP server {server_name}: {str(e)}")
            return []
            
    def get_server_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get status of all servers.
        
        Returns:
            Dictionary with server status information
        """
        status = {}
        
        for server_name, server_info in self.servers.items():
            server_type = server_info["type"]
            
            if server_type == "command":
                process = server_info.get("process")
                is_running = process and process.poll() is None
                pid = process.pid if process else None
            else:
                is_running = True  # SSE and HTTP servers are external
                pid = None
                
            uptime = time.time() - server_info["start_time"]
            
            status[server_name] = {
                "type": server_type,
                "running": is_running,
                "uptime": uptime,
                "pid": pid,
                "config": server_info["config"]
            }
            
        return status
        
    def stop_servers(self):
        """
        Stop all servers.
        """
        for server_name, process in self.processes.items():
            try:
                logger.info(f"Stopping server: {server_name}")
                process.terminate()
                process.wait(timeout=10)
                logger.info(f"Server stopped: {server_name}")
            except subprocess.TimeoutExpired:
                logger.warning(f"Server {server_name} did not terminate gracefully, killing it")
                process.kill()
            except Exception as e:
                logger.error(f"Error stopping server {server_name}: {str(e)}")


class MCPProxyServer:
    """
    HTTP proxy server that exposes MCP servers as REST endpoints.
    """
    
    def __init__(self, config_path: str, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
        """
        Initialize the MCP proxy server.
        
        Args:
            config_path: Path to the configuration file
            host: Host to bind the server to
            port: Port to listen on
        """
        self.config_path = config_path
        self.host = host
        self.port = port
        self.config = None
        self.server_manager = None
        self.httpd = None
        self.shutdown_requested = False
        
        # Load configuration
        self._load_config()
        
        # Initialize server manager
        self.server_manager = MCPServerManager(self.config)
        
    def _load_config(self):
        """
        Load the configuration from the specified file.
        """
        try:
            with open(self.config_path, 'r') as f:
                self.config = json.load(f)
                logger.info(f"Configuration loaded from {self.config_path}")
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Failed to load configuration: {str(e)}")
            sys.exit(1)
            
    def start(self):
        """
        Start the MCP proxy server.
        """
        # Start MCP servers
        logger.info("Starting MCP servers...")
        self.server_manager.start_servers()
        
        # Create HTTP server
        handler = self._create_request_handler()
        self.httpd = socketserver.ThreadingTCPServer((self.host, self.port), handler)
        self.httpd.daemon_threads = True
        
        logger.info(f"MCP proxy server started at http://{self.host}:{self.port}")
        
        # Set up signal handlers for graceful shutdown
        def signal_handler(sig, frame):
            logger.info(f"Received signal {sig}, shutting down...")
            self.shutdown()
            
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Start the server
        try:
            self.httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            self.shutdown()
            
    def shutdown(self):
        """
        Shutdown the proxy server and all MCP servers.
        """
        if self.shutdown_requested:
            return
            
        self.shutdown_requested = True
        logger.info("Shutting down MCP proxy server...")
        
        # Stop HTTP server
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            
        # Stop MCP servers
        if self.server_manager:
            self.server_manager.stop_servers()
            
        logger.info("MCP proxy server stopped")
        
    def _create_request_handler(self):
        """
        Create a request handler for the proxy server.
        
        Returns:
            Request handler class
        """
        proxy_server = self
        
        class MCPProxyHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == '/':
                    # Return server information
                    self._send_json_response({
                        "name": "MCP Proxy Server",
                        "version": "1.0.0",
                        "servers": list(proxy_server.server_manager.servers.keys()),
                        "endpoints": [f"/{name}" for name in proxy_server.server_manager.servers.keys()]
                    })
                elif self.path == '/status':
                    # Return server status
                    status = proxy_server.server_manager.get_server_status()
                    self._send_json_response(status)
                elif self.path.startswith('/') and len(self.path) > 1:
                    # Handle server-specific GET requests (list tools)
                    server_name = self.path[1:].split('/')[0]
                    
                    if server_name in proxy_server.server_manager.servers:
                        try:
                            tools = proxy_server.server_manager.list_tools(server_name)
                            self._send_json_response({
                                "server": server_name,
                                "tools": tools
                            })
                        except Exception as e:
                            self._send_error_response(500, f"Error listing tools: {str(e)}")
                    else:
                        self._send_error_response(404, f"Server not found: {server_name}")
                else:
                    self._send_error_response(404, "Not found")
                    
            def do_POST(self):
                if self.path.startswith('/') and len(self.path) > 1:
                    # Handle tool calls
                    path_parts = self.path[1:].split('/')
                    server_name = path_parts[0]
                    
                    if server_name in proxy_server.server_manager.servers:
                        try:
                            # Read request body
                            content_length = int(self.headers.get('Content-Length', 0))
                            request_body = self.rfile.read(content_length).decode('utf-8')
                            request_data = json.loads(request_body)
                            
                            # Extract tool name and arguments
                            tool_name = request_data.get('tool')
                            arguments = request_data.get('arguments', {})
                            
                            if not tool_name:
                                self._send_error_response(400, "Missing 'tool' parameter")
                                return
                                
                            # Call the tool
                            result = proxy_server.server_manager.call_tool(server_name, tool_name, arguments)
                            self._send_json_response({
                                "server": server_name,
                                "tool": tool_name,
                                "result": result
                            })
                            
                        except json.JSONDecodeError:
                            self._send_error_response(400, "Invalid JSON in request body")
                        except Exception as e:
                            self._send_error_response(500, f"Error calling tool: {str(e)}")
                    else:
                        self._send_error_response(404, f"Server not found: {server_name}")
                else:
                    self._send_error_response(404, "Not found")
                    
            def _send_json_response(self, data: Dict[str, Any], status_code: int = 200):
                """Send a JSON response."""
                self.send_response(status_code)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
                self.send_header('Access-Control-Allow-Headers', 'Content-Type')
                self.end_headers()
                self.wfile.write(json.dumps(data, indent=2).encode('utf-8'))
                
            def _send_error_response(self, status_code: int, message: str):
                """Send an error response."""
                self._send_json_response({
                    "error": {
                        "code": status_code,
                        "message": message
                    }
                }, status_code)
                
            def do_OPTIONS(self):
                """Handle CORS preflight requests."""
                self.send_response(200)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
                self.send_header('Access-Control-Allow-Headers', 'Content-Type')
                self.end_headers()
                
            def log_message(self, format, *args):
                logger.info(f"{self.client_address[0]} - {format % args}")
                
        return MCPProxyHandler


def main():
    """Main entry point for the MCP proxy server."""
    parser = argparse.ArgumentParser(description="MCP Proxy Server - HTTP Gateway for MCP servers")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="Path to configuration file")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Host to bind the server to")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to listen on")
    args = parser.parse_args()
    
    # Configure logging
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.getLogger().setLevel(log_level)
    logger.info(f"Starting MCP proxy server with log level: {log_level}")
    
    # Create and start the proxy server
    server = MCPProxyServer(
        config_path=args.config,
        host=args.host,
        port=args.port
    )
    
    try:
        server.start()
    except Exception as e:
        logger.error(f"Error running MCP proxy server: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()