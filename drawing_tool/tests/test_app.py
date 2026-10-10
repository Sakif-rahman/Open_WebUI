import io
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

temporary = tempfile.TemporaryDirectory()
os.environ["DRAWING_API_KEY"] = "test-only-" + "a" * 48
os.environ["DRAWING_OUTPUT_DIR"] = temporary.name

from fastapi.testclient import TestClient
from PIL import Image
import app


class DrawingTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app.app)
        self.auth = {"Authorization": f"Bearer {app.API_KEY}"}
        self.drawing = {
            "title": "Test picture", "width": 256, "height": 256,
            "shapes": [{"kind": "rectangle", "x": 10, "y": 10, "x2": 80, "y2": 80, "fill": "#ff0000"}],
        }

    def tearDown(self):
        self.client.close()
        for path in Path(temporary.name).iterdir():
            path.unlink()

    def test_authentication_required_for_schema_and_generation(self):
        for headers in ({}, {"Authorization": "Bearer wrong"}):
            self.assertEqual(self.client.get("/openapi.json", headers=headers).status_code, 401)
            self.assertEqual(self.client.post("/draw", headers=headers, json=self.drawing).status_code, 401)
        self.assertEqual(self.client.get("/health").status_code, 200)

    def test_schema_has_exactly_one_authenticated_tool(self):
        schema = self.client.get("/openapi.json", headers=self.auth).json()
        self.assertEqual(list(schema["paths"]), ["/draw"])
        self.assertEqual(schema["paths"]["/draw"]["post"]["operationId"], "draw_image")
        self.assertEqual(schema["paths"]["/draw"]["post"]["security"], [{"HTTPBearer": []}])

    def test_generates_real_png_and_browser_link(self):
        response = self.client.post("/draw", headers=self.auth, json=self.drawing)
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        parsed = urlsplit(result["image_url"])
        image = self.client.get(f"{parsed.path}?{parsed.query}")
        self.assertEqual(image.status_code, 200)
        decoded = Image.open(io.BytesIO(image.content))
        self.assertEqual(decoded.format, "PNG")
        self.assertEqual(decoded.size, (256, 256))
        self.assertEqual(decoded.getpixel((30, 30)), (255, 0, 0))
        self.assertNotIn(app.API_KEY, result["image_url"])
        self.assertIn(result["image_url"], result["markdown"])

    def test_all_primitives_render(self):
        self.drawing["shapes"] += [
            {"kind": "ellipse", "x": 100, "y": 20, "x2": 150, "y2": 70},
            {"kind": "line", "x": 0, "y": 100, "x2": 200, "y2": 100},
            {"kind": "polygon", "points": [[10, 150], [50, 120], [90, 150]]},
            {"kind": "text", "x": 10, "y": 200, "text": "Hello", "font_size": 20},
        ]
        response = self.client.post("/draw", headers=self.auth, json=self.drawing)
        self.assertEqual(response.status_code, 200, response.text)

    def test_invalid_and_excessive_input_rejected(self):
        invalid = [
            {"width": 999999}, {"background": "not-a-color"}, {"shapes": []},
            {"shapes": [{"kind": "rectangle", "x": 100, "x2": 10}]},
            {"shapes": [{"kind": "polygon", "points": [[0, 0]]}]},
            {"shapes": [{"kind": "text", "text": ""}]},
            {"shapes": self.drawing["shapes"] * 201},
            {"unknown": "ignored parameters must not be accepted"},
        ]
        for changes in invalid:
            with self.subTest(changes=changes):
                self.assertEqual(self.client.post("/draw", headers=self.auth, json=self.drawing | changes).status_code, 422)

    def test_links_cannot_be_forged_or_used_after_expiry(self):
        result = self.client.post("/draw", headers=self.auth, json=self.drawing).json()
        parsed = urlsplit(result["image_url"])
        self.assertEqual(self.client.get(f"{parsed.path}?expires={result['expires_at']}&signature={'0' * 64}").status_code, 403)
        with patch("app.time.time", return_value=result["expires_at"] + 1):
            self.assertEqual(self.client.get(f"{parsed.path}?{parsed.query}").status_code, 403)
        image_id = "0" * 32
        expires = int(time.time()) + 60
        self.assertEqual(self.client.get(f"/images/{image_id}.png?expires={expires}&signature={app.signature(image_id, expires)}").status_code, 404)

    def test_storage_cap(self):
        with patch("app.MAX_IMAGES", 0):
            self.assertEqual(self.client.post("/draw", headers=self.auth, json=self.drawing).status_code, 507)
        self.assertEqual(list(Path(temporary.name).iterdir()), [])

    def test_each_request_gets_its_own_file(self):
        first = self.client.post("/draw", headers=self.auth, json=self.drawing).json()
        second = self.client.post("/draw", headers=self.auth, json=self.drawing).json()
        self.assertNotEqual(first["image_url"], second["image_url"])
        self.assertEqual(len(list(Path(temporary.name).glob("*.png"))), 2)


if __name__ == "__main__":
    unittest.main()
