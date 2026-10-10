# Verification record

Verified on 2026-10-10 using Docker Desktop's Linux engine on Windows.

| Check | Result |
| --- | --- |
| Open WebUI | Version 0.11.4, healthy, available at `http://localhost:3000` |
| Drawing Studio | Built from this repository, healthy, available at `http://localhost:8001` |
| Runtime dependencies | `pip check`: no broken requirements |
| Unit tests | Eight passed in the isolated test image |
| Persistent connection | `drawing-studio`, OpenAPI, bearer authentication enabled |
| Repeat registration | Exactly one Drawing Studio connection after registering again |
| Unauthorized requests | Schema discovery and drawing generation rejected with HTTP 401 |
| Open WebUI integration | Discovered `draw_image` and invoked it through the installed `execute_tool_server` function |
| Generated output | PNG decoded successfully; dimensions and known pixel colors verified |
| Browser-facing URL | Signed image downloaded successfully through the published local port |
| Model-driven test | Existing Groq connection with `openai/gpt-oss-20b` generated valid drawing arguments and returned the actual image Markdown |
| Secrets | Runtime environment files ignored by Git; no provider keys copied into source |

The deterministic smoke test generated this image:

![Drawing generated through Open WebUI's tool executor](drawing-example.png)

The optional model test generated this image from a natural-language sunrise request:

![Drawing generated from model-supplied tool arguments](model-example.png)

The model test sends two requests to the existing provider: one to generate tool arguments, and one to incorporate the actual tool response into the answer. The tool call itself uses Open WebUI's installed executor and saved connection. Interactive browser chat behavior was not automated; enable Drawing Studio in the chat's Tools menu as described in the README.

Run the documented tests to reproduce these checks. The committed example PNGs contain no credentials or expiring signed URLs.
