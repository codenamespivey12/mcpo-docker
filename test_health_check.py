#!/usr/bin/env python3
"""
Test script for the health check and process monitoring functionality.
"""

import os
import json
import time
import tempfile
import unittest
import threading
import http.client
import subprocess
from unittest import mock
from health_check import HealthCheckServer
from process_monitor import ProcessMonitor


class TestHealthCheck(unittest.TestCase):
    """Test cases for the health check functionality."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a temporary config file
        self.temp_config = {
            "mcpServers": {
                "test-server": {
                    "command": "echo",
                    "args": ["test"],
                    "disabled": False
                }
            },
            "proxy": {
                "port": 8000,
                "host": "127.0.0.1"
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(self.temp_config, f)
            self.config_path = f.name
    
    def tearDown(self):
        """Clean up test environment."""
        if hasattr(self, 'config_path') and os.path.exists(self.config_path):
            os.unlink(self.config_path)
    
    @mock.patch('health_check.urlopen')
    def test_check_mcp_servers(self, mock_urlopen):
        """Test checking MCP server health."""
        # Mock the response from urlopen
        mock_response = mock.MagicMock()
        mock_response.status = 200
        mock_urlopen.return_value = mock_response
        
        # Create health check server
        server = HealthCheckServer(config_path=self.config_path, port=0)  # Use port 0 to avoid conflicts
        
        # Check MCP servers
        results = server.check_mcp_servers()
        
        # Verify results
        self.assertIn('test-server', results)
        self.assertEqual(results['test-server']['status'], 'healthy')
        self.assertTrue(results['test-server']['healthy'])
        self.assertEqual(results['test-server']['message'], 'Server is responding')
    
    @mock.patch('health_check.urlopen')
    def test_unhealthy_server(self, mock_urlopen):
        """Test handling of unhealthy MCP server."""
        # Mock the response from urlopen to simulate an error
        mock_urlopen.side_effect = Exception("Connection refused")
        
        # Create health check server
        server = HealthCheckServer(config_path=self.config_path, port=0)
        
        # Check MCP servers
        results = server.check_mcp_servers()
        
        # Verify results
        self.assertIn('test-server', results)
        self.assertEqual(results['test-server']['status'], 'unknown')
        self.assertFalse(results['test-server']['healthy'])
        self.assertIn('Error checking server health', results['test-server']['message'])
    
    def test_check_system_resources(self):
        """Test checking system resources."""
        # Create health check server
        server = HealthCheckServer(config_path=self.config_path, port=0)
        
        # Check system resources
        resources = server.check_system_resources()
        
        # Verify results
        self.assertIn('cpu_percent', resources)
        self.assertIn('memory_percent', resources)
        self.assertIn('process_count', resources)
    
    def test_get_health_status(self):
        """Test getting overall health status."""
        # Create health check server with mocked check_mcp_servers
        server = HealthCheckServer(config_path=self.config_path, port=0)
        server.check_mcp_servers = mock.MagicMock(return_value={
            'test-server': {
                'status': 'healthy',
                'healthy': True,
                'message': 'Server is responding'
            }
        })
        
        # Get health status
        status = server.get_health_status()
        
        # Verify results
        self.assertEqual(status['status'], 'healthy')
        self.assertIn('timestamp', status)
        self.assertIn('mcp_servers', status)
        self.assertIn('resources', status)
        self.assertEqual(status['config_path'], self.config_path)


class TestProcessMonitor(unittest.TestCase):
    """Test cases for the process monitoring functionality."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a temporary config file
        self.temp_config = {
            "mcpServers": {
                "test-server": {
                    "command": "sleep",
                    "args": ["0.1"],
                    "disabled": False
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(self.temp_config, f)
            self.config_path = f.name
    
    def tearDown(self):
        """Clean up test environment."""
        if hasattr(self, 'config_path') and os.path.exists(self.config_path):
            os.unlink(self.config_path)
    
    def test_start_processes(self):
        """Test starting processes."""
        # Create process monitor
        monitor = ProcessMonitor(config_path=self.config_path)
        
        # Start processes
        monitor.start_processes()
        
        # Verify processes were started
        self.assertIn('test-server', monitor.processes)
        self.assertIsNotNone(monitor.processes['test-server']['process'])
        
        # Clean up
        monitor.stop_processes()
    
    def test_monitor_processes(self):
        """Test monitoring processes."""
        # Create process monitor with short-lived process
        monitor = ProcessMonitor(
            config_path=self.config_path,
            check_interval=0.1,
            max_restarts=1,
            restart_delay=0.1
        )
        
        # Start processes
        monitor.start_processes()
        
        # Start monitoring in a separate thread
        monitor.running = True
        thread = threading.Thread(target=monitor.monitor_processes)
        thread.daemon = True
        thread.start()
        
        # Wait for the process to exit and be restarted
        time.sleep(0.5)
        
        # Stop monitoring
        monitor.running = False
        thread.join(timeout=1)
        
        # Verify the process was restarted
        self.assertEqual(monitor.restart_counts.get('test-server', 0), 1)
        
        # Clean up
        monitor.stop_processes()
    
    def test_get_process_status(self):
        """Test getting process status."""
        # Create process monitor
        monitor = ProcessMonitor(config_path=self.config_path)
        
        # Start processes
        monitor.start_processes()
        
        # Get process status
        status = monitor.get_process_status()
        
        # Verify results
        self.assertIn('test-server', status)
        self.assertIn('pid', status['test-server'])
        self.assertIn('running', status['test-server'])
        self.assertIn('uptime', status['test-server'])
        self.assertIn('restart_count', status['test-server'])
        
        # Clean up
        monitor.stop_processes()
    
    def test_graceful_shutdown(self):
        """Test graceful shutdown of processes."""
        # Create process monitor with longer-lived process
        self.temp_config["mcpServers"]["test-server"]["args"] = ["5"]
        with open(self.config_path, 'w') as f:
            json.dump(self.temp_config, f)
        
        monitor = ProcessMonitor(config_path=self.config_path)
        
        # Start processes
        monitor.start_processes()
        
        # Verify process is running
        self.assertIn('test-server', monitor.processes)
        process_info = monitor.processes['test-server']
        pid = process_info['process'].pid
        
        # Stop processes gracefully
        monitor.stop_processes(graceful=True)
        
        # Verify process was stopped
        self.assertNotIn('test-server', monitor.processes)
        
        # Check if the process is still running
        try:
            os.kill(pid, 0)
            process_exists = True
        except OSError:
            process_exists = False
        
        self.assertFalse(process_exists, "Process should have been terminated")


if __name__ == "__main__":
    unittest.main()