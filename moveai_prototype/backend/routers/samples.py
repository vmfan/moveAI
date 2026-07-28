"""Lists the sample images `routers/capture.py` resolves `image_name`
against, so the frontend's Capture UI has something to pick from instead of
requiring a blind filename (IMPLEMENTATION_ROADMAP.md Build 11).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

router = APIRouter(prefix="/api/samples", tags=["samples"])

APP_DIR = Path(__file__).resolve().parent.parent.parent
SAMPLE_DIR = APP_DIR.parent / "real_world_samples" / "images"


@router.get("")
def list_samples() -> list[dict]:
    names = sorted(p.name for p in SAMPLE_DIR.glob("*.jpg"))
    return [{"name": name, "url": f"/static/samples/{name}"} for name in names]
