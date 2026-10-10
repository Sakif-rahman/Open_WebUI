# Task requirements

> Spin up Open WebUI in Docker and connect one tool to it — specifically, a drawing/image-generation skill using either MCP or an OpenAPI tool server.
>
> A connected tool that can generate images on request.
>
> Authorization configured (API key / OAuth2 / service account).
>
> Clean, documented code pushed to a Git repository.

## Acceptance criteria

- Both Open WebUI and Drawing Studio run as healthy Docker Compose services.
- Open WebUI persistently discovers the `draw_image` operation from the drawing service's OpenAPI schema.
- The registered bearer key authorizes schema discovery and image generation; missing or incorrect keys fail.
- Executing the tool generates a valid PNG and a working browser-accessible image link.
- Setup is repeatable, preserves existing settings and does not commit credentials.
- README, dependencies, tests and verification steps are committed and pushed to `main`.

## Scope

The implementation is a local drawing skill: the chat model describes geometry, and Pillow renders it into PNGs. Photorealistic AI text-to-image generation is outside this implementation. Chat-based invocation uses the user's configured tool-capable language model.
