"""Authenticated OpenAPI drawing tool. No external image provider is required."""

import hashlib
import hmac
import os
import secrets
import threading
import time
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel, ConfigDict, Field, model_validator

API_KEY = os.environ.get("DRAWING_API_KEY", "")
if len(API_KEY) < 32 or API_KEY.startswith("replace-"):
    raise RuntimeError("Set DRAWING_API_KEY to a random secret of at least 32 characters")
PUBLIC_URL = os.environ.get("DRAWING_PUBLIC_URL", "http://localhost:8001").rstrip("/")
OUTPUT_DIR = Path(os.environ.get("DRAWING_OUTPUT_DIR", "/data"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
MAX_IMAGES = int(os.environ.get("DRAWING_MAX_IMAGES", "1000"))
LINK_TTL = 7 * 24 * 60 * 60
storage_lock = threading.Lock()
bearer = HTTPBearer(auto_error=False)


def authorize(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
    if credentials is None or not secrets.compare_digest(credentials.credentials, API_KEY):
        raise HTTPException(401, "Invalid or missing API key", headers={"WWW-Authenticate": "Bearer"})


app = FastAPI(
    title="Drawing Studio",
    version="1.0.0",
    description="Draw illustrations, diagrams and posters as PNG images using shapes and text.",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
Color = Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}$")]
Coordinate = Annotated[int, Field(ge=0, le=1536)]


class Shape(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["rectangle", "ellipse", "line", "polygon", "text"]
    x: Coordinate = 0
    y: Coordinate = 0
    x2: Coordinate = 100
    y2: Coordinate = 100
    fill: Color = "#2563eb"
    stroke: Color = "#111827"
    stroke_width: int = Field(default=2, ge=1, le=32)
    points: list[tuple[Coordinate, Coordinate]] = Field(default_factory=list, max_length=100)
    text: str = Field(default="", max_length=300)
    font_size: int = Field(default=24, ge=8, le=160)

    @model_validator(mode="after")
    def valid_geometry(self):
        if self.kind in {"rectangle", "ellipse"} and (self.x2 <= self.x or self.y2 <= self.y):
            raise ValueError("Rectangles and ellipses need x2 > x and y2 > y")
        if self.kind == "polygon" and len(self.points) < 3:
            raise ValueError("Polygons need at least three points")
        if self.kind == "text" and not self.text.strip():
            raise ValueError("Text shapes need nonempty text")
        return self


class Drawing(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=120, description="Short description of the requested drawing")
    width: int = Field(default=768, ge=128, le=1536)
    height: int = Field(default=768, ge=128, le=1536)
    background: Color = "#ffffff"
    shapes: list[Shape] = Field(min_length=1, max_length=200, description="Shapes in back-to-front order. Coordinates are pixels from the top-left. Rectangle/ellipse use x,y,x2,y2; line uses the same endpoints; polygon uses points; text uses x,y,text,font_size and fill. Use hex RGB colors.")


class DrawingResult(BaseModel):
    title: str
    image_url: str
    markdown: str
    width: int
    height: int
    expires_at: int


def signature(image_id: str, expires: int) -> str:
    return hmac.new(API_KEY.encode(), f"{image_id}:{expires}".encode(), hashlib.sha256).hexdigest()


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok"}


@app.get("/openapi.json", dependencies=[Depends(authorize)], include_in_schema=False)
def schema():
    return app.openapi()


@app.post("/draw", operation_id="draw_image", response_model=DrawingResult, dependencies=[Depends(authorize)])
def draw_image(drawing: Drawing):
    """Generate an actual PNG drawing for the user. Plan shapes and text to depict their
    request, then call this tool. Supports diagrams, simple illustrations and posters;
    it is a drawing renderer, not a photorealistic text-to-image model. Return the
    result's markdown verbatim to display the image. Do not invent an image URL.
    """
    canvas = Image.new("RGB", (drawing.width, drawing.height), drawing.background)
    painter = ImageDraw.Draw(canvas)
    for shape in drawing.shapes:
        box = (shape.x, shape.y, shape.x2, shape.y2)
        if shape.kind in {"rectangle", "ellipse"}:
            getattr(painter, shape.kind)(box, fill=shape.fill, outline=shape.stroke, width=shape.stroke_width)
        elif shape.kind == "line":
            painter.line(box, fill=shape.stroke, width=shape.stroke_width)
        elif shape.kind == "polygon":
            painter.polygon(shape.points, fill=shape.fill, outline=shape.stroke, width=shape.stroke_width)
        else:
            painter.text((shape.x, shape.y), shape.text, fill=shape.fill, font=ImageFont.load_default(size=shape.font_size))

    image_id = uuid4().hex
    with storage_lock:
        if sum(1 for _ in OUTPUT_DIR.glob("*.png")) >= MAX_IMAGES:
            raise HTTPException(507, "Image storage limit reached; archive or remove old images")
        temporary = OUTPUT_DIR / f"{image_id}.tmp"
        try:
            canvas.save(temporary, format="PNG")
            temporary.replace(OUTPUT_DIR / f"{image_id}.png")
        finally:
            temporary.unlink(missing_ok=True)
    expires = int(time.time()) + LINK_TTL
    url = f"{PUBLIC_URL}/images/{image_id}.png?expires={expires}&signature={signature(image_id, expires)}"
    return DrawingResult(title=drawing.title, image_url=url, markdown=f"![Generated drawing]({url})", width=drawing.width, height=drawing.height, expires_at=expires)


@app.get("/images/{image_id}.png", include_in_schema=False)
def image(image_id: UUID, expires: int, signature_value: Annotated[str, Query(alias="signature", pattern=r"^[0-9a-f]{64}$")]):
    if expires < int(time.time()) or not secrets.compare_digest(signature_value, signature(image_id.hex, expires)):
        raise HTTPException(403, "Invalid or expired image link")
    path = OUTPUT_DIR / f"{image_id.hex}.png"
    if not path.is_file():
        raise HTTPException(404, "Image not found")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer"})
