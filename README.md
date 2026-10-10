# Open WebUI

This repository contains Open WebUI backend source code and a Docker Compose configuration for running the published Open WebUI image locally.

## Quick start

Install Git and Docker with Docker Compose support. Make sure Docker is running, then clone the repository:

```sh
git clone https://github.com/Sakif-rahman/Open_WebUI.git
cd Open_WebUI
```

Create a file named `.env.open-webui` in the repository root. The Compose configuration requires this file; it can be empty for an initial launch. Add any deployment-specific environment settings there. This file is ignored by Git, so keep credentials and other private settings in it rather than committing them.

Start the service:

```sh
docker compose up -d
```

Open **http://localhost:3000** and follow the initial setup prompts. Configure your model provider in the application as needed; this Compose file does not start a model server.

## Deployment configuration

The settings in [compose.yaml](compose.yaml) provide:

| Setting | Value |
| --- | --- |
| Container image | `ghcr.io/open-webui/open-webui:main` |
| Local address | `127.0.0.1:3000`, forwarded to container port `8080` |
| Environment file | `.env.open-webui` |
| Persistent storage | Named volume `open-webui-data`, mounted at `/app/backend/data` |
| Restart policy | `unless-stopped` |
| Host access from the container | `host.docker.internal` mapped to the host gateway |

The port is bound to the local machine's loopback interface. Application data persists in the named Docker volume across container restarts and replacements.

## Common commands

Run these commands from the repository root:

```sh
# Show service status
docker compose ps

# Follow application logs
docker compose logs -f open-webui

# Stop and remove containers while keeping the data volume
docker compose down

# Download the published image and recreate the service
docker compose pull
docker compose up -d
```

Back up important application data before updating. Running `docker compose down -v` also deletes the named data volume.

## Repository layout

| Path | Purpose |
| --- | --- |
| `main.py` | FastAPI application entry point |
| `__init__.py` | Command-line entry points for serving and development |
| `config.py`, `env.py` | Application and environment configuration |
| `routers/` | API routes |
| `models/`, `internal/` | Data models and backend internals |
| `migrations/`, `alembic.ini` | Database migrations and Alembic configuration |
| `retrieval/` | Retrieval-related code |
| `socket/` | Real-time communication code |
| `storage/` | Storage integrations |
| `utils/`, `tools/` | Supporting utilities and tools |
| `static/` | Static assets |
| `compose.yaml` | Local Docker deployment configuration |

## Working with the source

The Compose service uses a published image. It does not build this checkout or mount the local Python source, so editing files here will not change the running container.

This checkout does not include a Python dependency manifest, a Dockerfile, or a frontend build project. Running or packaging the backend directly requires the matching dependencies and frontend assets to be supplied separately. The Docker Compose setup above is the included runnable deployment path.
