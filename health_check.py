#!/usr/bin/env python3
"""
Health check script for MCP Docker container.
Checks the health of all MCP servers and provides a unified health status.
Integrates with process monitoring for comprehensive container health management.

This module provides:
1. HTTP endpoints for container health checks:
   - /health: Overall container health status
   - /readiness: Container readiness check
   - /liveness: Container liveness check
   - /metrics: Prometheus-compatible metrics
   - /status: Detailed status of all MCP servers and processes
2. Integration with process monitoring for MCP servers
3. Structured logging for debugging with JSON or text format
4. Graceful shutdown handling with proper signal processing
5. Resource usage monitoring and reporting
"""

import os
import sys
import json
import time
import signal
import logging
import argparse
import subprocess
import http.server
import socketserver
import threading
from typing import Dict, Any, List, Tuple, Optional
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from pathlib import Path

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
            
            if hasattr(record, "process_name"):
                log_record["process_name"] = record.process_name
                
            if hasattr(record, "process_id"):
                log_record["process_id"] = record.process_id
                
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

logger = logging.getLogger("health_check")

# Default configuration
DEFAULT_CONFIG_PATH = os.environ.get("CONFIG_PATH", "/app/config.json")
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8080
DEFAULT_CHECK_INTERVAL = 30  # seconds


class HealthCheckServer:
    """
    HTTP server that provides health check endpoints for the MCP Docker container.
    Integrates with process monitoring for comprehensive health checks.
    """
    
    def __init__(self, config_path: str, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT,
                 check_interval: int = DEFAULT_CHECK_INTERVAL):
        """
        Initialize the health check server.
        
        Args:
            config_path: Path to the configuration file
            host: Host to bind the server to
            port: Port to listen on
            check_interval: Interval between health checks in seconds
        """
        self.config_path = config_path
        self.host = host
        self.port = port
        self.check_interval = check_interval
        self.config = None
        self.mcp_servers_status = {}
        self.process_status = {}
        self.last_check_time = 0
        self.is_healthy = True
        self.shutdown_requested = False
        self.process_monitor = None
        self.httpd = None
        self.start_time = time.time()
        
        # Load initial configuration
        self._load_config()
        
        # Initialize process monitor integration
        try:
            from process_monitor import ProcessMonitor
            self.process_monitor = ProcessMonitor(config_path=config_path)
            logger.info("Process monitor integration enabled")
        except ImportError:
            logger.warning("Process monitor module not found, process monitoring integration disabled")
            self.process_monitor = None
        
    def _load_config(self) -> Dict[str, Any]:
        """
        Load the configuration from the specified file.
        
        Returns:
            The loaded configuration as a dictionary
        """
        try:
            with open(self.config_path, 'r') as f:
                self.config = json.load(f)
                logger.info(f"Configuration loaded from {self.config_path}")
                return self.config
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Failed to load configuration: {str(e)}")
            self.is_healthy = False
            return {}
            
    def check_mcp_servers(self) -> Dict[str, Dict[str, Any]]:
        """
        Check the health of all MCP servers.
        
        Returns:
            Dictionary with health status for each MCP server
        """
        if not self.config or "mcpServers" not in self.config:
            logger.error("No MCP servers configured")
            self.is_healthy = False
            return {}
            
        mcp_servers = self.config.get("mcpServers", {})
        results = {}
        overall_healthy = True
        
        # Get proxy configuration
        proxy_config = self.config.get("proxy", {})
        proxy_port = proxy_config.get("port", 8000)
        proxy_host = proxy_config.get("host", "0.0.0.0")
        
        # Check each MCP server
        for server_name, server_config in mcp_servers.items():
            # Skip disabled servers
            if server_config.get("disabled", False):
                results[server_name] = {
                    "status": "disabled",
                    "healthy": True,
                    "message": "Server is disabled"
                }
                continue
                
            # Check if the server is responding
            try:
                # Try to access the server through the proxy
                url = f"http://{proxy_host}:{proxy_port}/health?server={server_name}"
                req = Request(url)
                response = urlopen(req, timeout=5)
                
                if response.status == 200:
                    results[server_name] = {
                        "status": "healthy",
                        "healthy": True,
                        "message": "Server is responding"
                    }
                else:
                    results[server_name] = {
                        "status": "unhealthy",
                        "healthy": False,
                        "message": f"Server returned status code {response.status}"
                    }
                    overall_healthy = False
            except (URLError, HTTPError) as e:
                results[server_name] = {
                    "status": "unhealthy",
                    "healthy": False,
                    "message": f"Failed to connect to server: {str(e)}"
                }
                overall_healthy = False
            except Exception as e:
                results[server_name] = {
                    "status": "unknown",
                    "healthy": False,
                    "message": f"Error checking server health: {str(e)}"
                }
                overall_healthy = False
                
        self.mcp_servers_status = results
        self.is_healthy = overall_healthy
        self.last_check_time = time.time()
        
        return results
        
    def check_system_resources(self) -> Dict[str, Any]:
        """
        Check system resource usage.
        
        Returns:
            Dictionary with system resource metrics
        """
        try:
            # Platform-specific commands
            if sys.platform == 'darwin':  # macOS
                cpu_cmd = ["ps", "-eo", "pcpu"]
                mem_cmd = ["ps", "-eo", "pmem"]
                proc_cmd = ["ps", "-e"]
            else:  # Linux and others
                cpu_cmd = ["ps", "-eo", "pcpu", "--no-headers"]
                mem_cmd = ["ps", "-eo", "pmem", "--no-headers"]
                proc_cmd = ["ps", "-e", "--no-headers"]
            
            # Get CPU usage
            cpu_percent = 0
            try:
                cpu_output = subprocess.check_output(cpu_cmd, universal_newlines=True)
                cpu_lines = cpu_output.strip().split('\n')
                
                # Skip header on macOS
                if sys.platform == 'darwin' and len(cpu_lines) > 0:
                    cpu_lines = cpu_lines[1:]
                    
                cpu_values = [float(x.strip()) for x in cpu_lines if x.strip()]
                cpu_percent = sum(cpu_values)
            except (subprocess.SubprocessError, ValueError) as e:
                logger.warning(f"Failed to get CPU usage: {str(e)}")
                cpu_percent = 0
                
            # Get memory usage
            memory_percent = 0
            try:
                mem_output = subprocess.check_output(mem_cmd, universal_newlines=True)
                mem_lines = mem_output.strip().split('\n')
                
                # Skip header on macOS
                if sys.platform == 'darwin' and len(mem_lines) > 0:
                    mem_lines = mem_lines[1:]
                    
                mem_values = [float(x.strip()) for x in mem_lines if x.strip()]
                memory_percent = sum(mem_values)
            except (subprocess.SubprocessError, ValueError) as e:
                logger.warning(f"Failed to get memory usage: {str(e)}")
                memory_percent = 0
                
            # Get process count
            process_count = 0
            try:
                ps_output = subprocess.check_output(proc_cmd, universal_newlines=True)
                ps_lines = ps_output.strip().split('\n')
                
                # Skip header on macOS
                if sys.platform == 'darwin' and len(ps_lines) > 0:
                    ps_lines = ps_lines[1:]
                    
                process_count = len([x for x in ps_lines if x.strip()])
            except subprocess.SubprocessError as e:
                logger.warning(f"Failed to get process count: {str(e)}")
                process_count = 0
                
            # Get disk usage
            disk_percent = 0
            try:
                if sys.platform == 'darwin':  # macOS
                    df_cmd = ["df", "-h", "/"]
                else:  # Linux and others
                    df_cmd = ["df", "-h", "/app"]
                    
                df_output = subprocess.check_output(df_cmd, universal_newlines=True)
                df_lines = df_output.strip().split('\n')
                
                if len(df_lines) > 1:
                    # Parse the percentage from the output (format varies by platform)
                    parts = df_lines[1].split()
                    for part in parts:
                        if part.endswith('%'):
                            disk_percent = float(part.rstrip('%'))
                            break
            except (subprocess.SubprocessError, ValueError, IndexError) as e:
                logger.warning(f"Failed to get disk usage: {str(e)}")
                disk_percent = 0
                
            return {
                "cpu_percent": cpu_percent,
                "memory_percent": memory_percent,
                "process_count": process_count,
                "disk_percent": disk_percent
            }
        except Exception as e:
            logger.error(f"Error checking system resources: {str(e)}")
            return {
                "cpu_percent": 0,
                "memory_percent": 0,
                "process_count": 0,
                "disk_percent": 0,
                "error": str(e)
            }
            
    def get_health_status(self) -> Dict[str, Any]:
        """
        Get the overall health status of the container.
        
        Returns:
            Dictionary with health status information
        """
        # Check if we need to refresh the health status
        current_time = time.time()
        if current_time - self.last_check_time > self.check_interval:
            self.check_mcp_servers()
            
        # Get system resources
        resources = self.check_system_resources()
        
        # Build health status response
        return {
            "status": "healthy" if self.is_healthy else "unhealthy",
            "timestamp": int(current_time),
            "mcp_servers": self.mcp_servers_status,
            "resources": resources,
            "config_path": self.config_path
        }
        
    def start(self):
        """
        Start the health check server.
        """
        handler = self._create_request_handler()
        
        # Create the server
        self.httpd = socketserver.ThreadingTCPServer((self.host, self.port), handler)
        self.httpd.daemon_threads = True  # Allow threads to exit when main thread exits
        
        logger.info(f"Health check server started at http://{self.host}:{self.port}")
        
        # Set up signal handlers for graceful shutdown
        def signal_handler(sig, frame):
            logger.info(f"Received signal {sig}, shutting down...")
            self.shutdown()
            
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Start the server in a separate thread
        server_thread = threading.Thread(target=self.httpd.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        
        # If process monitor is available, start it
        if self.process_monitor:
            self.process_monitor.start_processes()
            self.process_monitor.start_monitoring()
            
        # Keep the main thread alive
        try:
            while not self.shutdown_requested:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            self.shutdown()
            
    def shutdown(self):
        """
        Shutdown the health check server and all monitored processes.
        """
        if self.shutdown_requested:
            return
            
        self.shutdown_requested = True
        logger.info("Shutting down health check server...")
        
        # Stop the process monitor if available
        if self.process_monitor:
            logger.info("Stopping process monitor...")
            self.process_monitor.stop_monitoring()
            self.process_monitor.stop_processes(graceful=True)
            
        # Stop the HTTP server
        if self.httpd:
            logger.info("Stopping HTTP server...")
            self.httpd.shutdown()
            self.httpd.server_close()
            
        logger.info("Health check server stopped")
                
    def get_detailed_status(self) -> Dict[str, Any]:
        """
        Get detailed status information about the container and all MCP servers.
        
        Returns:
            Dictionary with detailed status information
        """
        # Get health status
        health_status = self.get_health_status()
        
        # Get process status if process monitor is available
        process_status = {}
        if self.process_monitor:
            process_status = self.process_monitor.get_process_status()
        
        # Calculate uptime
        uptime = time.time() - self.start_time
        
        # Build detailed status response
        return {
            "status": health_status["status"],
            "uptime": uptime,
            "timestamp": int(time.time()),
            "mcp_servers": health_status["mcp_servers"],
            "processes": process_status,
            "resources": health_status["resources"],
            "config_path": self.config_path,
            "config_loaded": self.config is not None,
            "process_monitor_enabled": self.process_monitor is not None
        }
    
    def _create_request_handler(self):
        """
        Create a request handler for the health check server.
        
        Returns:
            Request handler class
        """
        health_check_server = self
        
        class HealthCheckHandler(http.server.SimpleHTTPRequestHandler):
            def do_GET(self):
                if self.path == '/health' or self.path == '/':
                    # Get health status
                    health_status = health_check_server.get_health_status()
                    
                    # Set response headers
                    self.send_response(200 if health_check_server.is_healthy else 503)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    
                    # Send response
                    self.wfile.write(json.dumps(health_status).encode('utf-8'))
                elif self.path == '/status':
                    # Get detailed status
                    detailed_status = health_check_server.get_detailed_status()
                    
                    # Set response headers
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    
                    # Send response
                    self.wfile.write(json.dumps(detailed_status).encode('utf-8'))
                elif self.path == '/readiness':
                    # Check if configuration is loaded
                    if health_check_server.config is not None:
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({"status": "ready"}).encode('utf-8'))
                    else:
                        self.send_response(503)
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({"status": "not ready"}).encode('utf-8'))
                elif self.path == '/liveness':
                    # Always return 200 if the server is running
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "alive"}).encode('utf-8'))
                elif self.path == '/metrics':
                    # Get system resources
                    resources = health_check_server.check_system_resources()
                    
                    # Set response headers
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/plain')
                    self.end_headers()
                    
                    # Format metrics in Prometheus format
                    metrics = [
                        f"# HELP mcpo_cpu_percent CPU usage percentage",
                        f"# TYPE mcpo_cpu_percent gauge",
                        f"mcpo_cpu_percent {resources['cpu_percent']}",
                        f"# HELP mcpo_memory_percent Memory usage percentage",
                        f"# TYPE mcpo_memory_percent gauge",
                        f"mcpo_memory_percent {resources['memory_percent']}",
                        f"# HELP mcpo_process_count Number of processes",
                        f"# TYPE mcpo_process_count gauge",
                        f"mcpo_process_count {resources['process_count']}",
                        f"# HELP mcpo_uptime_seconds Container uptime in seconds",
                        f"# TYPE mcpo_uptime_seconds counter",
                        f"mcpo_uptime_seconds {time.time() - health_check_server.start_time}"
                    ]
                    
                    # Add metrics for each MCP server
                    metrics.append(f"# HELP mcpo_server_status MCP server status (1=healthy, 0=unhealthy)")
                    metrics.append(f"# TYPE mcpo_server_status gauge")
                    
                    for server_name, status in health_check_server.mcp_servers_status.items():
                        value = 1 if status.get("healthy", False) else 0
                        metrics.append(f'mcpo_server_status{{server="{server_name}"}} {value}')
                    
                    # Add process metrics if process monitor is available
                    if health_check_server.process_monitor:
                        process_status = health_check_server.process_monitor.get_process_status()
                        metrics.append(f"# HELP mcpo_process_running Process running status (1=running, 0=stopped)")
                        metrics.append(f"# TYPE mcpo_process_running gauge")
                        metrics.append(f"# HELP mcpo_process_restart_count Process restart count")
                        metrics.append(f"# TYPE mcpo_process_restart_count counter")
                        metrics.append(f"# HELP mcpo_process_uptime_seconds Process uptime in seconds")
                        metrics.append(f"# TYPE mcpo_process_uptime_seconds counter")
                        
                        for server_name, status in process_status.items():
                            running = 1 if status.get("running", False) else 0
                            metrics.append(f'mcpo_process_running{{process="{server_name}"}} {running}')
                            metrics.append(f'mcpo_process_restart_count{{process="{server_name}"}} {status.get("restart_count", 0)}')
                            metrics.append(f'mcpo_process_uptime_seconds{{process="{server_name}"}} {status.get("uptime", 0)}')
                    
                    # Send response
                    self.wfile.write('\n'.join(metrics).encode('utf-8'))
                else:
                    self.send_error(404)
                    
            def log_message(self, format, *args):
                logger.info(f"{self.client_address[0]} - {format % args}")
                
        return HealthCheckHandler


def main():
    """Main entry point for the health check server."""
    parser = argparse.ArgumentParser(description="Health check server for MCP Docker container")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="Path to configuration file")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Host to bind the server to")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to listen on")
    parser.add_argument("--interval", type=int, default=DEFAULT_CHECK_INTERVAL, help="Interval between health checks in seconds")
    parser.add_argument("--no-process-monitor", action="store_true", help="Disable process monitoring")
    args = parser.parse_args()
    
    # Configure logging
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.getLogger().setLevel(log_level)
    logger.info(f"Starting health check server with log level: {log_level}")
    
    # Create and start the health check server
    server = HealthCheckServer(
        config_path=args.config,
        host=args.host,
        port=args.port,
        check_interval=args.interval
    )
    
    # Start the server
    try:
        server.start()
    except KeyboardInterrupt:
        logger.info("Interrupted by user, shutting down...")
        server.shutdown()
    except Exception as e:
        logger.error(f"Error running health check server: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()