#!/usr/bin/env python3
"""
Process monitoring script for MCP Docker container.
Monitors MCP server processes and restarts them if they fail.

This module provides:
1. Automatic monitoring and restarting of MCP server processes
2. Graceful shutdown handling with proper signal processing
3. Structured logging for debugging with JSON or text format
4. Process status reporting for health checks
5. Resource usage monitoring for individual processes
"""

import os
import sys
import json
import time
import signal
import logging
import argparse
import subprocess
import threading
from typing import Dict, Any, List, Tuple, Optional
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

logger = logging.getLogger("process_monitor")

# Default configuration
DEFAULT_CONFIG_PATH = os.environ.get("CONFIG_PATH", "/app/config.json")
DEFAULT_CHECK_INTERVAL = 10  # seconds
DEFAULT_MAX_RESTARTS = 3  # maximum number of restarts per process
DEFAULT_RESTART_DELAY = 5  # seconds to wait before restarting a process


class ProcessMonitor:
    """
    Monitors MCP server processes and restarts them if they fail.
    """
    
    def __init__(self, config_path: str, check_interval: int = DEFAULT_CHECK_INTERVAL,
                 max_restarts: int = DEFAULT_MAX_RESTARTS, restart_delay: int = DEFAULT_RESTART_DELAY):
        """
        Initialize the process monitor.
        
        Args:
            config_path: Path to the configuration file
            check_interval: Interval between process checks in seconds
            max_restarts: Maximum number of restarts per process
            restart_delay: Seconds to wait before restarting a process
        """
        self.config_path = config_path
        self.check_interval = check_interval
        self.max_restarts = max_restarts
        self.restart_delay = restart_delay
        self.config = None
        self.processes = {}  # Dictionary of process name -> process object
        self.restart_counts = {}  # Dictionary of process name -> restart count
        self.running = False
        self.monitor_thread = None
        
        # Load initial configuration
        self._load_config()
        
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
            return {}
            
    def start_processes(self):
        """
        Start all MCP server processes defined in the configuration.
        """
        if not self.config or "mcpServers" not in self.config:
            logger.error("No MCP servers configured")
            return
            
        mcp_servers = self.config.get("mcpServers", {})
        
        for server_name, server_config in mcp_servers.items():
            # Skip disabled servers
            if server_config.get("disabled", False):
                logger.info(f"Skipping disabled server: {server_name}")
                continue
                
            # Start the server process
            self._start_process(server_name, server_config)
            
    def _start_process(self, server_name: str, server_config: Dict[str, Any]) -> bool:
        """
        Start a single MCP server process.
        
        Args:
            server_name: Name of the server
            server_config: Server configuration
            
        Returns:
            True if the process was started successfully, False otherwise
        """
        try:
            command = server_config.get("command")
            args = server_config.get("args", [])
            env_vars = server_config.get("env", {})
            
            if not command:
                logger.error(f"No command specified for server: {server_name}")
                return False
                
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
                    env[key] = value
            
            # Start the process
            cmd = [command] + args
            logger.info(f"Starting process: {server_name} - {' '.join(cmd)}")
            
            # Use temp files for stdout and stderr to avoid resource leaks
            stdout_file = open(os.devnull, 'w')
            stderr_file = open(os.devnull, 'w')
            
            process = subprocess.Popen(
                cmd,
                env=env,
                stdout=stdout_file,
                stderr=stderr_file,
                universal_newlines=True,
                bufsize=1  # Line buffered
            )
            
            # Store the process and file handles
            self.processes[server_name] = {
                "process": process,
                "command": cmd,
                "env": env,
                "start_time": time.time(),
                "stdout_file": stdout_file,
                "stderr_file": stderr_file
            }
            
            # Initialize restart count
            if server_name not in self.restart_counts:
                self.restart_counts[server_name] = 0
            
            logger.info(f"Process started: {server_name} (PID: {process.pid})")
            return True
        except Exception as e:
            logger.error(f"Failed to start process {server_name}: {str(e)}")
            return False
            
    def _monitor_output(self, server_name: str, pipe, pipe_name: str):
        """
        Monitor process output and log it.
        
        Args:
            server_name: Name of the server
            pipe: Process output pipe (stdout or stderr)
            pipe_name: Name of the pipe ("stdout" or "stderr")
        """
        try:
            for line in pipe:
                line = line.rstrip()
                if pipe_name == "stdout":
                    logger.info(f"[{server_name}] {line}")
                else:
                    logger.error(f"[{server_name}] {line}")
        except Exception as e:
            logger.error(f"Error monitoring {pipe_name} for {server_name}: {str(e)}")
            
    def monitor_processes(self):
        """
        Monitor all processes and restart them if they fail.
        """
        while self.running:
            for server_name, process_info in list(self.processes.items()):
                process = process_info["process"]
                
                # Check if the process is still running
                if process.poll() is not None:
                    exit_code = process.returncode
                    logger.warning(f"Process {server_name} exited with code {exit_code}")
                    
                    # Close file handles
                    if "stdout_file" in process_info and process_info["stdout_file"]:
                        process_info["stdout_file"].close()
                    
                    if "stderr_file" in process_info and process_info["stderr_file"]:
                        process_info["stderr_file"].close()
                    
                    # Remove the process from the list
                    del self.processes[server_name]
                    
                    # Check if we should restart the process
                    if self.restart_counts[server_name] < self.max_restarts:
                        logger.info(f"Restarting process {server_name} (attempt {self.restart_counts[server_name] + 1}/{self.max_restarts})")
                        
                        # Increment restart count
                        self.restart_counts[server_name] += 1
                        
                        # Wait before restarting
                        time.sleep(self.restart_delay)
                        
                        # Get server configuration
                        server_config = self.config.get("mcpServers", {}).get(server_name)
                        if server_config:
                            # Start the process
                            self._start_process(server_name, server_config)
                        else:
                            logger.error(f"Server configuration not found for {server_name}")
                    else:
                        logger.error(f"Process {server_name} has been restarted {self.restart_counts[server_name]} times, giving up")
            
            # Wait before checking again
            time.sleep(self.check_interval)
            
    def start_monitoring(self):
        """
        Start the process monitoring thread.
        """
        if self.monitor_thread is not None and self.monitor_thread.is_alive():
            logger.warning("Process monitoring is already running")
            return
            
        self.running = True
        self.monitor_thread = threading.Thread(target=self.monitor_processes)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        logger.info("Process monitoring started")
        
    def stop_monitoring(self):
        """
        Stop the process monitoring thread.
        """
        self.running = False
        if self.monitor_thread is not None:
            self.monitor_thread.join(timeout=5)
            logger.info("Process monitoring stopped")
            
    def stop_processes(self, graceful: bool = True):
        """
        Stop all processes.
        
        Args:
            graceful: Whether to stop processes gracefully (SIGTERM) or forcefully (SIGKILL)
        """
        for server_name, process_info in list(self.processes.items()):
            process = process_info["process"]
            
            try:
                if graceful:
                    logger.info(f"Gracefully stopping process {server_name} (PID: {process.pid})")
                    process.terminate()  # Send SIGTERM
                    
                    # Wait for the process to terminate
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        logger.warning(f"Process {server_name} did not terminate gracefully, killing it")
                        process.kill()  # Send SIGKILL
                else:
                    logger.info(f"Forcefully stopping process {server_name} (PID: {process.pid})")
                    process.kill()  # Send SIGKILL
                
                # Close file handles
                if "stdout_file" in process_info and process_info["stdout_file"]:
                    process_info["stdout_file"].close()
                
                if "stderr_file" in process_info and process_info["stderr_file"]:
                    process_info["stderr_file"].close()
                
                # Remove the process from the list
                del self.processes[server_name]
                logger.info(f"Process {server_name} stopped")
            except Exception as e:
                logger.error(f"Error stopping process {server_name}: {str(e)}")
                
    def get_process_resource_usage(self, pid: int) -> Dict[str, float]:
        """
        Get resource usage for a specific process.
        
        Args:
            pid: Process ID
            
        Returns:
            Dictionary with resource usage information
        """
        try:
            # Get CPU and memory usage using ps (platform-specific)
            if sys.platform == 'darwin':  # macOS
                cmd = ["ps", "-p", str(pid), "-o", "%cpu,%mem"]
            else:  # Linux and others
                cmd = ["ps", "-p", str(pid), "-o", "%cpu,%mem", "--no-headers"]
                
            output = subprocess.check_output(cmd, universal_newlines=True).strip()
            
            # Parse the output
            lines = output.split('\n')
            if len(lines) > 1:  # Skip header on macOS
                values = lines[1].strip().split()
            else:
                values = lines[0].strip().split()
                
            if len(values) >= 2:
                try:
                    cpu_percent = float(values[0])
                    mem_percent = float(values[1])
                    return {
                        "cpu_percent": cpu_percent,
                        "memory_percent": mem_percent
                    }
                except (ValueError, IndexError):
                    pass
                    
            return {
                "cpu_percent": 0.0,
                "memory_percent": 0.0
            }
        except (subprocess.SubprocessError, ValueError, IndexError) as e:
            logger.warning(f"Failed to get resource usage for PID {pid}: {str(e)}")
            return {
                "cpu_percent": 0.0,
                "memory_percent": 0.0
            }
    
    def get_process_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get the status of all processes.
        
        Returns:
            Dictionary with process status information
        """
        status = {}
        
        for server_name, process_info in self.processes.items():
            process = process_info["process"]
            
            # Check if the process is still running
            is_running = process.poll() is None
            
            # Calculate uptime
            uptime = time.time() - process_info["start_time"]
            
            # Get resource usage if the process is running
            resource_usage = {}
            if is_running:
                resource_usage = self.get_process_resource_usage(process.pid)
            
            status[server_name] = {
                "pid": process.pid,
                "running": is_running,
                "uptime": uptime,
                "restart_count": self.restart_counts.get(server_name, 0),
                "command": process_info["command"],
                "cpu_percent": resource_usage.get("cpu_percent", 0.0),
                "memory_percent": resource_usage.get("memory_percent", 0.0)
            }
            
        return status


def main():
    """Main entry point for the process monitor."""
    parser = argparse.ArgumentParser(description="Process monitor for MCP Docker container")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="Path to configuration file")
    parser.add_argument("--interval", type=int, default=DEFAULT_CHECK_INTERVAL, help="Interval between process checks in seconds")
    parser.add_argument("--max-restarts", type=int, default=DEFAULT_MAX_RESTARTS, help="Maximum number of restarts per process")
    parser.add_argument("--restart-delay", type=int, default=DEFAULT_RESTART_DELAY, help="Seconds to wait before restarting a process")
    parser.add_argument("--log-level", default=os.environ.get("LOG_LEVEL", "INFO").upper(), help="Logging level")
    args = parser.parse_args()
    
    # Configure logging
    logging.getLogger().setLevel(args.log_level)
    logger.info(f"Starting process monitor with log level: {args.log_level}")
    
    # Create the process monitor
    monitor = ProcessMonitor(
        config_path=args.config,
        check_interval=args.interval,
        max_restarts=args.max_restarts,
        restart_delay=args.restart_delay
    )
    
    # Set up signal handlers for graceful shutdown
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}, shutting down...")
        monitor.stop_monitoring()
        monitor.stop_processes(graceful=True)
        sys.exit(0)
        
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start processes and monitoring
    try:
        logger.info("Starting MCP server processes...")
        monitor.start_processes()
        
        logger.info("Starting process monitoring...")
        monitor.start_monitoring()
        
        # Keep the main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Interrupted by user, shutting down...")
    except Exception as e:
        logger.error(f"Error running process monitor: {str(e)}")
        sys.exit(1)
    finally:
        logger.info("Stopping process monitoring...")
        monitor.stop_monitoring()
        
        logger.info("Stopping MCP server processes...")
        monitor.stop_processes(graceful=True)
        
        logger.info("Process monitor shutdown complete")


if __name__ == "__main__":
    main()