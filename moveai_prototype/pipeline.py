from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

import numpy as np
from PIL import Image, ImageOps

from config import PipelineConfig
from geometry import MeasurementFailure, ObjectMeasurement, measure_all
from models import (
    Detection,
    best_device,
    detect_furniture,
    estimate_metric_depth,
    release_memory,
    segment_detections,
)


ProgressCallback = Callable[[str, float], None]


@dataclass
class PipelineResult:
    image: Image.Image
    detections: list[Detection]
    depth_m: np.ndarray
    focal_length_px: float
    measurements: list[ObjectMeasurement]
    measurement_errors: list[MeasurementFailure]
    timings_s: dict[str, float] = field(default_factory=dict)

    @property
    def total_visible_volume_m3(self) -> float:
        return sum(item.visible_obb_volume_m3 for item in self.measurements)


def prepare_image(image: Image.Image, max_side: int = 1_280) -> Image.Image:
    image = ImageOps.exif_transpose(image).convert("RGB")
    if max(image.size) <= max_side:
        return image
    scale = max_side / max(image.size)
    return image.resize(
        (round(image.width * scale), round(image.height * scale)),
        Image.Resampling.LANCZOS,
    )


def run_pipeline(
    image: Image.Image,
    furniture_classes: list[str],
    config: PipelineConfig,
    progress: ProgressCallback | None = None,
) -> PipelineResult:
    progress = progress or (lambda _message, _value: None)
    image = prepare_image(image)
    device = best_device()
    timings: dict[str, float] = {}

    progress(f"Grounding DINO: detecting furniture on {device.type.upper()}", 0.08)
    start = time.perf_counter()
    detections = detect_furniture(image, furniture_classes, config, device)
    timings["Grounding DINO"] = time.perf_counter() - start
    release_memory()

    if not detections:
        raise RuntimeError(
            "Grounding DINO found no requested furniture. "
            "Try lowering the box threshold or changing the class prompts."
        )

    progress(f"SAM 2: segmenting {len(detections)} detected items", 0.33)
    start = time.perf_counter()
    detections = segment_detections(image, detections, device)
    timings["SAM 2"] = time.perf_counter() - start
    release_memory()

    progress("Depth Pro: estimating metric depth and focal length", 0.58)
    start = time.perf_counter()
    depth_m, focal_length_px = estimate_metric_depth(image, config, device)
    timings["Depth Pro"] = time.perf_counter() - start
    release_memory()

    progress("Open3D: fitting visible-surface bounding boxes", 0.88)
    start = time.perf_counter()
    measurements, errors = measure_all(
        image,
        depth_m,
        focal_length_px,
        detections,
        config,
    )
    timings["Open3D"] = time.perf_counter() - start

    progress("Analysis complete", 1.0)
    return PipelineResult(
        image=image,
        detections=detections,
        depth_m=depth_m,
        focal_length_px=focal_length_px,
        measurements=measurements,
        measurement_errors=errors,
        timings_s=timings,
    )

