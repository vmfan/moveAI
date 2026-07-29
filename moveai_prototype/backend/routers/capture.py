"""Wires the AI pipeline behind `POST /api/jobs/{job_id}/capture`, plus lazy
GET endpoints serving the four artifacts `app.py`'s tabs already render
(overlay, depth, point cloud, inventory) -- IMPLEMENTATION_ROADMAP.md
Build 10.

The image is resolved only against `real_world_samples/images/` (basename
only, no path traversal) -- a real image-source picker (upload / URL /
webcam) remains out of scope; this endpoint only needs the sample set wired
end-to-end.

Multi-image build: `POST` now accepts a batch of `image_names`, running the
pipeline once per image (each still gets its own DB rows and its own
in-memory artifact cache entry, keyed by `(job_id, image_name)` --
`serialization.py`), then automatically runs the cross-image dedup +
room-labeling pass (`backend/dedup.py`) once every image in the batch has
been persisted. A dedup failure (e.g. the HKUST endpoint is unreachable)
does not roll back the batch -- the capture has already succeeded and is
persisted; the failure is surfaced as `dedup_error` in the response instead.
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
from backend import dedup, pipeline_runtime, reasoning_client, serialization  # noqa: E402
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


def _get_result_or_404(job_id: int, image_name: str):
    result = serialization.get_result(job_id, image_name)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No capture has run yet for job {job_id!r}, image {image_name!r}",
        )
    return result


@router.post("")
def capture(
    payload: CaptureIn,
    job: dict = Depends(deps.get_job_or_404),
    conn: sqlite3.Connection = Depends(deps.get_conn),
) -> dict:
    if not payload.image_names:
        raise HTTPException(status_code=422, detail="image_names must be non-empty")

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

    per_image_summaries: dict[str, dict] = {}
    batch_captures: list[dedup.CaptureBatchImage] = []

    for image_name in payload.image_names:
        image_path = _resolve_sample_image(image_name)
        image = Image.open(image_path)

        result = pipeline_runtime.run_pipeline_locked(image, furniture_classes, config)
        serialization.store_result(job["id"], image_path.name, result)

        summary = inventory_sync.persist_capture(
            conn,
            job["id"],
            measurements=result.measurements,
            failures=result.measurement_errors,
            room_label=payload.room_label,
            source_image_name=image_path.name,
            focal_length_px=result.focal_length_px,
        )
        per_image_summaries[image_path.name] = {
            **summary,
            "timings_s": result.timings_s,
            "total_visible_volume_m3": result.total_visible_volume_m3,
        }
        batch_captures.append(
            dedup.CaptureBatchImage(
                image_name=image_path.name,
                result=result,
                measured_item_ids=summary["measured_item_ids"],
                room_label=payload.room_label,
            )
        )

        if job["status"] == "capture":
            db.set_job_status(conn, job["id"], "inventory_review")
            job = {**job, "status": "inventory_review"}

    dedup_result: dict = {"duplicates_removed": [], "room_labels_assigned": {}}
    dedup_error: str | None = None
    if len(batch_captures) >= 2:
        try:
            dedup_result = dedup.run_dedup_and_labeling(conn, job["id"], batch_captures)
        except reasoning_client.ReasoningClientError as exc:
            dedup_error = str(exc)

    return {
        "images": per_image_summaries,
        "duplicates_removed": dedup_result["duplicates_removed"],
        "room_labels_assigned": dedup_result["room_labels_assigned"],
        "dedup_error": dedup_error,
        "artifacts": {
            "overlay_url_template": f"/api/jobs/{job['id']}/capture/overlay.png?image_name={{image_name}}",
            "depth_url_template": f"/api/jobs/{job['id']}/capture/depth.png?image_name={{image_name}}",
            "inventory_url": f"/api/jobs/{job['id']}/capture/inventory",
            "point_cloud_url_template": f"/api/jobs/{job['id']}/capture/points/{{item_index}}?image_name={{image_name}}",
            "images_url": f"/api/jobs/{job['id']}/capture/images",
        },
    }


@router.get("/images")
def list_captured_images(job: dict = Depends(deps.get_job_or_404)) -> dict:
    results = serialization.list_results_for_job(job["id"])
    return {"image_names": sorted(results.keys())}


@router.get("/overlay.png")
def overlay(
    image_name: str, job: dict = Depends(deps.get_job_or_404)
) -> Response:
    result = _get_result_or_404(job["id"], image_name)
    return Response(content=serialization.overlay_png(result), media_type="image/png")


@router.get("/depth.png")
def depth(
    image_name: str, job: dict = Depends(deps.get_job_or_404)
) -> Response:
    result = _get_result_or_404(job["id"], image_name)
    return Response(content=serialization.depth_png(result), media_type="image/png")


@router.get("/inventory")
def inventory(job: dict = Depends(deps.get_job_or_404)) -> dict:
    results = serialization.list_results_for_job(job["id"])
    if not results:
        raise HTTPException(
            status_code=404, detail=f"No capture has run yet for job {job['id']!r}"
        )
    return serialization.combined_inventory_json(results)


@router.get("/points/{item_index}")
def points(
    item_index: int, image_name: str, job: dict = Depends(deps.get_job_or_404)
) -> Response:
    result = _get_result_or_404(job["id"], image_name)
    try:
        payload = serialization.point_cloud_json(result, item_index)
    except IndexError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(content=payload, media_type="application/json")
