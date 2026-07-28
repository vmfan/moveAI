"""Wires the AI pipeline behind `POST /api/jobs/{job_id}/capture`, plus lazy
GET endpoints serving the four artifacts `app.py`'s tabs already render
(overlay, depth, point cloud, inventory) -- IMPLEMENTATION_ROADMAP.md
Build 10.

The image is resolved only against `real_world_samples/images/` (basename
only, no path traversal) for this build -- a real image-source picker
(upload / URL / webcam) is Build 11's Capture UI scope; this endpoint only
needs one real sample wired end-to-end.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response
from PIL import Image

from backend import deps
from backend.schemas import CaptureIn

import db  # noqa: E402
import inventory_sync  # noqa: E402
from backend import pipeline_runtime, serialization  # noqa: E402
from config import DEFAULT_FURNITURE_CLASSES, PipelineConfig  # noqa: E402

router = APIRouter(prefix="/api/jobs/{job_id}/capture", tags=["capture"])

APP_DIR = Path(__file__).resolve().parent.parent.parent
SAMPLE_DIR = APP_DIR.parent / "real_world_samples" / "images"


def _resolve_sample_image(image_name: str) -> Path:
    path = SAMPLE_DIR / Path(image_name).name
    if not path.is_file():
        raise HTTPException(
            status_code=404, detail=f"No sample image named {image_name!r}"
        )
    return path


def _get_result_or_404(job_id: int):
    result = serialization.get_result(job_id)
    if result is None:
        raise HTTPException(
            status_code=404, detail=f"No capture has run yet for job {job_id!r}"
        )
    return result


@router.post("")
def capture(
    payload: CaptureIn,
    job: dict = Depends(deps.get_job_or_404),
    conn: sqlite3.Connection = Depends(deps.get_conn),
) -> dict:
    image_path = _resolve_sample_image(payload.image_name)
    image = Image.open(image_path)

    config = PipelineConfig(
        **{
            key: value
            for key, value in (
                ("box_threshold", payload.box_threshold),
                ("max_detections", payload.max_detections),
            )
            if value is not None
        }
    )
    furniture_classes = payload.furniture_classes or DEFAULT_FURNITURE_CLASSES

    result = pipeline_runtime.run_pipeline_locked(image, furniture_classes, config)
    serialization.store_result(job["id"], result)

    summary = inventory_sync.persist_capture(
        conn,
        job["id"],
        measurements=result.measurements,
        failures=result.measurement_errors,
        room_label=payload.room_label,
        source_image_name=image_path.name,
        focal_length_px=result.focal_length_px,
    )
    if job["status"] == "capture":
        db.set_job_status(conn, job["id"], "inventory_review")

    return {
        **summary,
        "timings_s": result.timings_s,
        "total_visible_volume_m3": result.total_visible_volume_m3,
        "artifacts": {
            "overlay_url": f"/api/jobs/{job['id']}/capture/overlay.png",
            "depth_url": f"/api/jobs/{job['id']}/capture/depth.png",
            "inventory_url": f"/api/jobs/{job['id']}/capture/inventory",
            "point_cloud_url_template": f"/api/jobs/{job['id']}/capture/points/{{item_index}}",
        },
    }


@router.get("/overlay.png")
def overlay(job: dict = Depends(deps.get_job_or_404)) -> Response:
    result = _get_result_or_404(job["id"])
    return Response(content=serialization.overlay_png(result), media_type="image/png")


@router.get("/depth.png")
def depth(job: dict = Depends(deps.get_job_or_404)) -> Response:
    result = _get_result_or_404(job["id"])
    return Response(content=serialization.depth_png(result), media_type="image/png")


@router.get("/inventory")
def inventory(job: dict = Depends(deps.get_job_or_404)) -> dict:
    result = _get_result_or_404(job["id"])
    return serialization.inventory_json(result)


@router.get("/points/{item_index}")
def points(item_index: int, job: dict = Depends(deps.get_job_or_404)) -> Response:
    result = _get_result_or_404(job["id"])
    try:
        payload = serialization.point_cloud_json(result, item_index)
    except IndexError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(content=payload, media_type="application/json")
