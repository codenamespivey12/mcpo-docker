# mcpo-docker

An example Docker image for [mcpo](https://github.com/open-webui/mcpo), a tool that exposes MCP (Model Context Protocol) servers as OpenAPI-compatible HTTP endpoints for [OpenWebUI](https://github.com/open-webui/open-webui).

> Still waiting for the official mcpo docker!

## Quick start

```shell
# Pull the repo
git clone https://github.com/alephpiece/mcpo-docker.git
cd mcpo-docker

# Copy sample files and edit them as you like.
cp config.example.json config.json
cp docker-compose.example.yml docker-compose.yml

# Create a container and wait for the servers to start.
# It may take time if you have many servers enabled.
docker compose up -d
```

Or you can build the docker from source.

```shell
docker build -t mcpo .
```

### Connect OpenWebUI to your servers

> See [OpenAPI Tool Servers](https://docs.openwebui.com/openapi-servers/) for details.

1. Open OpenWebUI > Settings > Tools
2. Add a connection `http://localhost:8000/memory`
3. Check available tools on the chat page

With mcpo, each MCP server gets a separate endpoint. For example:

- `http://localhost:8000/sequential-thinking`
- `http://localhost:8000/memory`
- `http://localhost:8000/time`

## MCP configuration

Standard MCP configuration file, see [config.example.json](./config.example.json).

## License

MIT