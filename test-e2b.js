// Test script for E2B MCP server initialization
const { spawn } = require('child_process');
const path = require('path');

// Function to test E2B MCP server initialization
async function testE2BMCPServer() {
  console.log('Testing E2B MCP server initialization...');

  // Check if E2B_API_KEY is set
  if (!process.env.E2B_API_KEY) {
    console.error('Error: E2B_API_KEY environment variable is not set');
    console.error('Please set the E2B_API_KEY environment variable and try again');
    console.error('Example: export E2B_API_KEY=your_api_key_here');
    process.exit(1);
  }

  // Spawn the E2B MCP server process
  const e2bProcess = spawn('uvx', ['e2b-mcp-server'], {
    env: {
      ...process.env,
      E2B_API_KEY: process.env.E2B_API_KEY
    }
  });

  // Set a timeout to kill the process after 5 seconds (just for testing)
  const timeout = setTimeout(() => {
    console.log('Test completed. Terminating E2B MCP server...');
    e2bProcess.kill();
    console.log('E2B MCP server initialization test passed!');
    process.exit(0);
  }, 5000);

  // Handle process output
  e2bProcess.stdout.on('data', (data) => {
    console.log(`E2B MCP server output: ${data}`);
  });

  e2bProcess.stderr.on('data', (data) => {
    console.error(`E2B MCP server error: ${data}`);
    clearTimeout(timeout);
    e2bProcess.kill();
    process.exit(1);
  });

  // Handle process exit
  e2bProcess.on('close', (code) => {
    if (code !== 0 && code !== null) {
      console.error(`E2B MCP server exited with code ${code}`);
      process.exit(1);
    }
  });
}

// Run the test
testE2BMCPServer().catch(err => {
  console.error('Test failed:', err);
  process.exit(1);
});