# Open WebUI + Drawing Studio

Run Open WebUI in Docker with an authenticated OpenAPI tool that creates PNG drawings. A tool-capable chat model supplies shapes and text to `draw_image`; the tool renders an image locally and returns Markdown for displaying it in chat.

Drawing Studio supports rectangles, ellipses, lines, polygons and text. It requires no paid image API. This is a drawing skill, not a photorealistic text-to-image model. Natural-language chat requests still require a configured language model.

## Requirements

| Task requirement | Implementation |
| --- | --- |
| Open WebUI in Docker | Service pinned to the tested Open WebUI 0.11.4 image digest |
| One connected drawing tool | Drawing Studio OpenAPI server, with one `draw_image` operation |
| Authorization | Random 256-bit bearer key for discovery and generation |
| Documented code | Setup script, dependencies, tests and verification instructions |

The original checkout had no dependency requirements file. New dependencies are in [drawing_tool/requirements.txt](drawing_tool/requirements.txt), with test dependencies in [requirements-dev.txt](drawing_tool/requirements-dev.txt). See [task requirements](docs/requirements.md).

## Start on Windows

Install Git and Docker Desktop with Linux containers and Docker Compose. Start Docker. Ports 3000 and 8001 must be available.

```powershell
git clone https://github.com/Sakif-rahman/Open_WebUI.git
cd Open_WebUI
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup.ps1
```

Setup creates ignored `.env.open-webui` and `.env.drawing` files with random secrets if they do not exist, builds the drawing service, waits for healthy services, and registers the tool. It uses the pinned Open WebUI application's `Config` model and restarts Open WebUI to refresh the tool cache. Existing accounts, settings and other tool connections are preserved. Re-running setup updates the same registration. Use `-SkipBuild` when the drawing code has not changed.

Open **http://localhost:3000**. Complete administrator setup on a fresh installation, or sign in with your existing account. [.env.example](.env.example) documents settings without real credentials. Never commit runtime environment files.

## Generate an image in chat

1. Select a model that supports tool calling. Configure a provider in Open WebUI's admin connection settings if needed.
2. In the chat composer, open **Integrations / Tools** and enable **Drawing Studio**.
3. Send: **Use Drawing Studio to draw a sunrise over green hills with a yellow sun and the words Good morning. Display the image returned by the tool.**

The result contains `image_url`, `markdown`, dimensions and expiration time. The model should include the returned Markdown in its answer. The [official integration guide](https://docs.openwebui.com/features/extensibility/plugin/tools/openapi-servers/open-webui/) explains global tool activation; tools must be enabled in the chat.

The registered backend URL is `http://drawing-tool:8000`, schema path `openapi.json`, authentication `bearer`. The browser image origin is `http://localhost:8001`. The backend runs inside Docker, so its tool URL must use the service name instead of localhost.

## Verification

```powershell
docker compose ps

# Unit tests in an isolated container
docker build --target test -t open-webui-drawing:test drawing_tool
docker run --rm open-webui-drawing:test

# Discover and execute the registered tool through Open WebUI
Get-Content -Raw scripts/smoke_test.py | docker compose exec -T open-webui python -

# Optional: also test model-generated arguments and the final image answer
# Uses the existing Groq connection and may consume provider quota.
Get-Content -Raw scripts/smoke_test.py | docker compose exec -T open-webui python - --with-model
```

The smoke test reads the saved connection, verifies rejection of unauthenticated requests, discovers `draw_image`, invokes Open WebUI's tool executor, downloads the signed image and checks its PNG dimensions and pixels. It prints a browser image URL. This verifies the integration independently of a model deciding to call a tool.

The optional model test uses the saved Groq credentials and `openai/gpt-oss-20b`. You can pass `DRAWING_TEST_PROVIDER_URL` and `DRAWING_TEST_MODEL` with `docker compose exec -e ...` to select another already-configured OpenAI-compatible provider. It calls the provider directly for the model steps and Open WebUI's executor for the tool step; it does not automate a browser chat.

Eight unit tests cover authentication, the OpenAPI security declaration, real PNG output, all primitives, invalid/excessive input, forged/expired links, storage limits and unique image files. See [verification results](docs/verification.md).

## Configuration and security

| Setting | Purpose |
| --- | --- |
| `DRAWING_API_KEY` | At least 32 characters; setup creates 64 random hex characters. Required for schema discovery and generation. |
| `DRAWING_PUBLIC_URL` | Browser-accessible image origin; defaults to `http://localhost:8001`. |
| `DRAWING_MAX_IMAGES` | Stored PNG limit; default 1000. Generation returns HTTP 507 when full. |
| `WEBUI_SECRET_KEY` | Open WebUI session secret; existing value is preserved. |

Images use unguessable IDs and HMAC-signed links that expire after seven days. Anyone holding a valid link can view that image until expiration; the link does not contain the bearer key. Download images you want to keep. Files persist after link expiration; archive or remove old images from the volume when it reaches its limit. Rotating `DRAWING_API_KEY` and rerunning setup updates both services and registration, and invalidates old image links.

The drawing container runs as a non-root user with a read-only root filesystem and no Linux capabilities. Inputs are limited to 128-1536 pixel dimensions and 200 shapes. The service accepts drawing data only: no executable code, remote files or model-supplied filesystem paths. `/health` is public; `/draw` and `/openapi.json` require bearer authorization. Browsers fetch images using signed links.

Both ports bind to `127.0.0.1`. This setup is for local use. Remote deployment requires an HTTPS reverse proxy and an externally reachable `DRAWING_PUBLIC_URL`.

## Operations and development

```powershell
docker compose logs --tail 100 drawing-tool open-webui
docker compose restart drawing-tool
docker compose down
```

`docker compose down` retains application data and drawings in the `open-webui-data` and `drawing-images` named volumes. Adding `-v` deletes those volumes. Back up data before upgrades or volume removal.

Edit `drawing_tool/app.py`, then rerun setup to rebuild. Open WebUI is pinned because registration uses its version-specific configuration model. Recheck registration and rerun the smoke test when upgrading.

| Path | Purpose |
| --- | --- |
| `drawing_tool/` | FastAPI/Pillow service, Dockerfile, dependencies and tests |
| `scripts/setup.ps1` | Repeatable deployment and secret generation |
| `scripts/register_tool.py` | Persistent registration inside Open WebUI |
| `scripts/smoke_test.py` | Verification using the installed tool executor |
| `compose.yaml` | Services, health checks, local ports and volumes |
| `docs/` | Requirements and verification record |
| `main.py`, `routers/`, `models/`, etc. | Original Open WebUI backend snapshot |

Compose runs the published Open WebUI image; it does not build or mount the original backend snapshot. The drawing service is built from this checkout. No upstream backend modifications are required.
