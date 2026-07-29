"""Turns a `PipelineResult`'s PIL images/numpy arrays into lazy per-artifact
payloads (IMPLEMENTATION_ROADMAP.md Build 10), mirroring the 4-tab layout
`app.py`'s analyze block already renders (overlay, depth, point cloud,
inventory) instead of shipping one giant response.

Results are kept in an in-memory, single-process cache keyed by
`(job_id, image_name)`, one entry per captured image -- a job's multi-image
batch (IMPLEMENTATION_ROADMAP.md multi-image build) keeps every image's
result available for its own artifact endpoints and for the dedup pass,
rather than only the single most recent capture.
"""

from __future__ import annotations

import io
import sys
import threading
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
APP_DIR = BACKEND_DIR.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from pipeline import PipelineResult  # noqa: E402
from visualization import (  # noqa: E402
    point_cloud_figure,
    render_depth_map,
    render_detection_overlay,
)

_lock = threading.Lock()
_results: dict[tuple[int, str], PipelineResult] = {}


def store_result(job_id: int, image_name: str, result: PipelineResult) -> None:
    with _lock:
        _results[(job_id, image_name)] = result


def get_result(job_id: int, image_name: str) -> PipelineResult | None:
    with _lock:
        return _results.get((job_id, image_name))


def list_results_for_job(job_id: int) -> dict[str, PipelineResult]:
    """All stored per-image results for a job, keyed by image_name."""
    with _lock:
        return {
            image_name: result
            for (result_job_id, image_name), result in _results.items()
            if result_job_id == job_id
        }


def overlay_png(result: PipelineResult) -> bytes:
    image = render_detection_overlay(result.image, result.detections)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def depth_png(result: PipelineResult) -> bytes:
    image = render_depth_map(result.depth_m)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def point_cloud_json(result: PipelineResult, item_index: int) -> str:
    """`item_index` is 1-based, matching the numbering `result_rows()` and
    the overlay's on-image labels already use."""
    if item_index < 1 or item_index > len(result.measurements):
        raise IndexError(f"No measured item at index {item_index!r}")
    measurement = result.measurements[item_index - 1]
    return point_cloud_figure(measurement).to_json()


def inventory_json(result: PipelineResult) -> dict:
    """Raw pipeline output for one image, not persisted DB rows -- distinct
    from the existing `/api/jobs/{id}/inventory` router, which reads what's
    actually been written to the database."""
    items = [
        {
            "index": index,
            "label": item.label,
            "detection_confidence": item.detection_score,
            "width_m": item.width_m,
            "height_m": item.height_m,
            "depth_m": item.depth_m,
            "visible_obb_volume_m3": item.visible_obb_volume_m3,
            "median_depth_m": item.median_depth_m,
            "point_count": item.point_count,
            "used_axis_aligned_fallback": item.used_axis_aligned_fallback,
            "mask_touches_border": item.mask_touches_border,
            "warning": item.warning,
        }
        for index, item in enumerate(result.measurements, start=1)
    ]
    errors = [
        {
            "index": failure.index,
            "label": failure.label,
            "detection_confidence": failure.detection_score,
            "message": failure.message,
        }
        for failure in result.measurement_errors
    ]
    return {
        "items": items,
        "errors": errors,
        "total_visible_volume_m3": result.total_visible_volume_m3,
        "timings_s": result.timings_s,
    }


def combined_inventory_json(results: dict[str, PipelineResult]) -> dict:
    """Merges `inventory_json()` across every image_name a job has a stored
    result for, tagging each item/error with its source image so a batch
    capture's preview shows every image at once instead of only the last
    one processed."""
    items: list[dict] = []
    errors: list[dict] = []
    total_volume = 0.0
    timings_s: dict[str, float] = {}
    for image_name, result in results.items():
        per_image = inventory_json(result)
        for item in per_image["items"]:
            items.append({**item, "source_image_name": image_name})
        for error in per_image["errors"]:
            errors.append({**error, "source_image_name": image_name})
        total_volume += per_image["total_visible_volume_m3"]
        timings_s[image_name] = per_image["timings_s"]
    return {
        "items": items,
        "errors": errors,
        "total_visible_volume_m3": total_volume,
        "timings_s": timings_s,
    }
