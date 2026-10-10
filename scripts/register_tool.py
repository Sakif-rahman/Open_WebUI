"""Run inside the pinned Open WebUI container as its deployment operator.

Uses the application's Config model; preserves other tools, users and settings.
Restart Open WebUI afterwards to refresh its in-process tool cache.
"""

import asyncio
import os

from open_webui.models.config import Config


async def register():
    key = os.environ["DRAWING_API_KEY"]
    if len(key) < 32:
        raise RuntimeError("DRAWING_API_KEY must have at least 32 characters")
    connections = await Config.get("tool_server.connections", []) or []
    connection = {
        "type": "openapi",
        "url": "http://drawing-tool:8000",
        "path": "openapi.json",
        "auth_type": "bearer",
        "key": key,
        "config": {"enable": True},
        "info": {"id": "drawing-studio", "name": "Drawing Studio", "description": "Generate PNG drawings, diagrams and posters from shapes and text."},
    }
    for index, item in enumerate(connections):
        if (item.get("info") or {}).get("id") == "drawing-studio":
            connections[index] = connection
            break
    else:
        connections.append(connection)
    await Config.upsert({"tool_server.connections": connections})
    print("Drawing Studio registered with bearer authentication. Other connections preserved.")


if __name__ == "__main__":
    asyncio.run(register())
