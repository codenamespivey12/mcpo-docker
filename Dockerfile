FROM python:3.11-slim

LABEL org.opencontainers.image.title="mcp-docker"
LABEL org.opencontainers.image.description="Docker image for multiple MCP (Model Context Protocol) servers"
LABEL org.opencontainers.image.source="https://github.com/lkoujiu/mcpo-docker"
LABEL org.opencontainers.image.licenses="MIT"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (using the official Node.js installation method)
RUN mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_18.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list \
    && apt-get update && apt-get install -y --no-install-recommends \
    nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g npm@latest

# Install uv package manager for Python
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="/usr/local/bin" sh

# Create app directory
WORKDIR /app

# Copy configuration files
COPY config.example.json /app/config.example.json

# Install common MCP server dependencies
RUN npm install -g @modelcontextprotocol/server-sequential-thinking \
    @modelcontextprotocol/server-memory \
    @upstash/context7-mcp \
    exa-mcp-server

# Install Python MCP server dependencies
RUN uv pip install mcp-server-time e2b-mcp-server

# Set environment variables
ENV NODE_ENV=production \
    CONFIG_PATH=/app/config.json \
    PORT=8000 \
    HOST=0.0.0.0

# Expose port for MCP server
EXPOSE 8000

# Copy all Python scripts
COPY health_check.py process_monitor.py mcp_proxy.py config_handler.py /app/

# Set up health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/status || exit 1

# Set entrypoint and default command
ENTRYPOINT ["python3"]
CMD ["/app/mcp_proxy.py", "--config", "/app/config.json"]