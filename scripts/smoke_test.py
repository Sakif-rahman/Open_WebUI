"""Run inside Open WebUI: discover and execute the registered OpenAPI tool."""

import asyncio
import io
import json
import os
import sys
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from PIL import Image
import requests
from open_webui.models.config import Config
from open_webui.utils.tools import execute_tool_server, get_tool_servers_data


async def main():
    connections = await Config.get("tool_server.connections", [])
    connection = next(c for c in connections if (c.get("info") or {}).get("id") == "drawing-studio")
    servers = await get_tool_servers_data([connection])
    assert len(servers) == 1, "Open WebUI could not discover Drawing Studio"
    server = servers[0]
    assert any(s["name"] == "draw_image" for s in server["specs"]), "Missing draw_image tool"
    for path in ("/openapi.json", "/draw"):
        request = urllib.request.Request(connection["url"] + path, data=b"{}" if path == "/draw" else None, headers={"Content-Type": "application/json"})
        try:
            urllib.request.urlopen(request, timeout=10)
            raise AssertionError("Unauthenticated request was accepted")
        except urllib.error.HTTPError as error:
            assert error.code == 401, f"Unexpected authentication status: {error.code}"
    drawing = {
        "title": "Sunrise over the hills", "width": 768, "height": 512, "background": "#dbeafe",
        "shapes": [
            {"kind": "ellipse", "x": 500, "y": 50, "x2": 650, "y2": 200, "fill": "#fbbf24", "stroke": "#fbbf24"},
            {"kind": "polygon", "points": [[0, 380], [230, 130], [470, 400]], "fill": "#64748b", "stroke": "#64748b"},
            {"kind": "polygon", "points": [[300, 400], [540, 220], [768, 400]], "fill": "#94a3b8", "stroke": "#94a3b8"},
            {"kind": "rectangle", "x": 0, "y": 390, "x2": 768, "y2": 512, "fill": "#22c55e", "stroke": "#22c55e"},
            {"kind": "text", "x": 32, "y": 440, "text": "Drawing Studio", "font_size": 36, "fill": "#ffffff"},
        ],
    }
    model_context = None
    if "--with-model" in sys.argv:
        provider = os.environ.get("DRAWING_TEST_PROVIDER_URL", "https://api.groq.com/openai/v1")
        model = os.environ.get("DRAWING_TEST_MODEL", "openai/gpt-oss-20b")
        urls = await Config.get("openai.api_base_urls", [])
        keys = await Config.get("openai.api_keys", [])
        index = urls.index(provider)
        headers = {"Authorization": "Bearer " + keys[index]}
        messages = [
            {"role": "system", "content": "Use the drawing tool for image requests. Always include the tool's returned markdown exactly in your final answer."},
            {"role": "user", "content": "Draw a simple cheerful sunrise over green hills, with a yellow sun and the words Good morning, as a 768 by 512 PNG. Use the drawing tool and display its result."},
        ]
        response = requests.post(
            provider + "/chat/completions",
            headers=headers,
            json={"model": model, "messages": messages, "tools": [{"type": "function", "function": server["specs"][0]}], "tool_choice": "required", "max_completion_tokens": 4096},
            timeout=90,
        )
        response.raise_for_status()
        message = response.json()["choices"][0]["message"]
        call = message["tool_calls"][0]
        assert call["function"]["name"] == "draw_image", "Model selected an unexpected tool"
        drawing = json.loads(call["function"]["arguments"])
        messages.append(message)
        model_context = (provider, model, headers, messages, call["id"])

    result, _ = await execute_tool_server(
        url=connection["url"],
        server_data=server,
        name="draw_image",
        params=drawing,
        headers={"Authorization": "Bearer " + connection["key"]},
        cookies={},
    )
    assert "image_url" in result, result
    parsed = urlsplit(result["image_url"])
    with urllib.request.urlopen(connection["url"] + parsed.path + "?" + parsed.query, timeout=10) as response:
        content = response.read()
    image = Image.open(io.BytesIO(content))
    assert image.format == "PNG" and image.size == (drawing.get("width", 768), drawing.get("height", 768))
    if model_context is None:
        assert image.getpixel((550, 100)) == (251, 191, 36)
    else:
        provider, model, headers, messages, call_id = model_context
        messages.append({"role": "tool", "tool_call_id": call_id, "content": json.dumps(result)})
        response = requests.post(
            provider + "/chat/completions",
            headers=headers,
            json={"model": model, "messages": messages, "max_completion_tokens": 1024},
            timeout=90,
        )
        response.raise_for_status()
        answer = response.json()["choices"][0]["message"]["content"]
        assert result["markdown"] in answer, "Model did not include the actual image Markdown"
        print("Model-generated drawing and final image Markdown verified:", model)
    print(json.dumps({"status": "passed", "checks": ["Open WebUI discovery", "bearer authentication", "Open WebUI tool execution", "signed image download", "PNG validation"], "image_url": result["image_url"]}))


if __name__ == "__main__":
    asyncio.run(main())
