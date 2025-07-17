// Simple test script for Context7 MCP server
const { spawn } = require('child_process');
const process = require('process');

console.log('Starting Context7 MCP server test...');

// Spawn the Context7 MCP server process
const context7Process = spawn('npx', ['-y', '@upstash/context7-mcp'], {
  stdio: ['ignore', 'pipe', 'pipe']
});

// Set a timeout to kill the process after 5 seconds
const timeout = setTimeout(() => {
  console.log('Test completed. Terminating Context7 MCP server.');
  context7Process.kill();
  process.exit(0);
}, 5000);

// Handle process output
context7Process.stdout.on('data', (data) => {
  console.log(`Context7 stdout: ${data}`);
});

context7Process.stderr.on('data', (data) => {
  console.log(`Context7 stderr: ${data}`);
});

// Handle process exit
context7Process.on('close', (code) => {
  clearTimeout(timeout);
  console.log(`Context7 MCP server process exited with code ${code}`);
  process.exit(code || 0);
});

// Handle errors
context7Process.on('error', (err) => {
  clearTimeout(timeout);
  console.error('Failed to start Context7 MCP server:', err);
  process.exit(1);
});