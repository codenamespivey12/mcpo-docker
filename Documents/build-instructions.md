# MCP Docker Build Instructions

This document provides instructions for building the MCP Docker container, which consolidates multiple Model Context Protocol (MCP) servers into a single deployable container.

## Prerequisites

Before building the Docker container, ensure you have the following dependencies installed on your system:

- Docker (20.10.0 or later)
- Docker Compose (optional, for deployment)
- Git (for cloning the repository)

## Basic Build Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/lkoujiu/mcpo-docker.git
cd mcpo-docker
```

### 2. Build the Docker Image

To build the Docker image with default settings:

```bash
docker build -t mcpo:latest .
```

This will create a Docker image named `mcpo` with the tag `latest`.

## Build Options

### Custom Tags

You can specify a custom tag for your Docker image:

```bash
docker build -t mcpo:v1.0.0 .
```

### Build Arguments

The Dockerfile supports several build arguments that can be used to customize the build:

```bash
docker build \
  --build-arg NODE_VERSION=18 \
  --build-arg PYTHON_VERSION=3.11 \
  -t mcpo:custom .
```

### Multi-Platform Builds

To build for multiple platforms (e.g., for ARM-based systems like Raspberry Pi):

```bash
docker buildx create --use
docker buildx build --platform linux/amd64,linux/arm64 -t mcpo:multi-arch .
```

## Advanced Build Scenarios

### Minimal Build

For a minimal build that only includes specific MCP servers, you can modify the Dockerfile:

1. Create a custom Dockerfile:

```bash
cp Dockerfile Dockerfile.minimal
```

2. Edit `Dockerfile.minimal` to remove unwanted MCP servers from the installation steps.

3. Build using the custom Dockerfile:

```bash
docker build -f Dockerfile.minimal -t mcpo:minimal .
```

### Development Build

For development purposes, you might want to include additional debugging tools:

```bash
docker build --build-arg NODE_ENV=development -t mcpo:dev .
```

### CI/CD Pipeline Build

For integration into CI/CD pipelines, you can use the following command:

```bash
docker build \
  --no-cache \
  --pull \
  -t mcpo:${CI_COMMIT_SHA} \
  .
```

## Dependency Requirements

The Docker container includes the following dependencies:

### System Dependencies
- Python 3.11
- Node.js 18.x
- curl, gnupg, ca-certificates

### Package Managers
- npm (Node.js package manager)
- uv (Python package manager)

### MCP Server Dependencies
- @modelcontextprotocol/server-sequential-thinking (Node.js)
- @modelcontextprotocol/server-memory (Node.js)
- mcp-server-time (Python)
- @upstash/context7-mcp (Node.js)
- e2b-mcp-server (Python)
- exa-mcp-server (Node.js)

## Verification

After building the Docker image, you can verify it was created successfully:

```bash
docker images | grep mcpo
```

You can also run a quick test to ensure the container starts properly:

```bash
docker run --rm -p 8000:8000 -v $(pwd)/config.example.json:/app/config.json mcpo:latest
```

## Troubleshooting Build Issues

### Common Build Errors

1. **Network Issues**:
   - Error: `Failed to fetch Node.js repository`
   - Solution: Check your internet connection and try again, or use `--network=host` flag

2. **Permission Issues**:
   - Error: `permission denied while trying to connect to the Docker daemon socket`
   - Solution: Add your user to the docker group or use sudo

3. **Disk Space Issues**:
   - Error: `no space left on device`
   - Solution: Clean up Docker system with `docker system prune -a`

### Build Optimization

To optimize the build process:

- Use Docker BuildKit: `DOCKER_BUILDKIT=1 docker build -t mcpo:latest .`
- Use build caching: Organize Dockerfile to maximize cache usage
- Consider multi-stage builds for smaller final images

## Next Steps

After successfully building the Docker image, refer to the Configuration Guide and Deployment Guide for instructions on how to configure and deploy the MCP Docker container.