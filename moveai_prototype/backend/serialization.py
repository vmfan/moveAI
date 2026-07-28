"""Turns a `PipelineResult`'s PIL images/numpy arrays into lazy per-artifact
payloads (IMPLEMENTATION_ROADMAP.md Build 10), mirroring the 4-tab layout
`app.py`'s analyze block already renders (overlay, depth, point cloud,
inventory) instead of shipping one giant response.

Results are kept in an in-memory, single-process cache keyed by job id,
holding only the most recent capture per job -- multi-capture artifact
history isn't needed yet, since only one capture path is wired this build.
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
_results: dict[int, PipelineResult] = {}


def store_result(job_id: int, result: PipelineResult) -> None:
    with _lock:
        _results[job_id] = result


def get_result(job_id: int) -> PipelineResult | None:
    with _lock:
        return _results.get(job_id)


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
    """Raw pipeline output, not persisted DB rows -- distinct from the
    existing `/api/jobs/{id}/inventory` router, which reads what's actually
    been written to the database."""
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
