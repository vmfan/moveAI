from __future__ import annotations

import gc
import math
import os
from dataclasses import dataclass
from typing import Sequence

os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from transformers import (
    AutoImageProcessor,
    AutoModelForDepthEstimation,
    AutoModelForZeroShotObjectDetection,
    AutoProcessor,
    Sam2Model,
    Sam2Processor,
)

from config import (
    DEPTH_ANYTHING_V2_MODEL,
    GROUNDING_DINO_MODEL,
    SAM2_MODEL,
    PipelineConfig,
)


@dataclass
class Detection:
    label: str
    score: float
    box: np.ndarray
    mask: np.ndarray | None = None


def best_device() -> torch.device:
    if torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def release_memory(*objects: object) -> None:
    for obj in objects:
        del obj
    gc.collect()
    if torch.backends.mps.is_available():
        torch.mps.empty_cache()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def _box_iou(box_a: np.ndarray, box_b: np.ndarray) -> float:
    x1 = max(float(box_a[0]), float(box_b[0]))
    y1 = max(float(box_a[1]), float(box_b[1]))
    x2 = min(float(box_a[2]), float(box_b[2]))
    y2 = min(float(box_a[3]), float(box_b[3]))
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area_a = max(0.0, float(box_a[2] - box_a[0])) * max(
        0.0, float(box_a[3] - box_a[1])
    )
    area_b = max(0.0, float(box_b[2] - box_b[0])) * max(
        0.0, float(box_b[3] - box_b[1])
    )
    union = area_a + area_b - intersection
    return intersection / union if union > 0 else 0.0


def _class_aware_nms(
    detections: list[Detection], iou_threshold: float
) -> list[Detection]:
    kept: list[Detection] = []
    for detection in sorted(detections, key=lambda item: item.score, reverse=True):
        duplicate = any(
            detection.label == other.label
            and _box_iou(detection.box, other.box) >= iou_threshold
            for other in kept
        )
        if not duplicate:
            kept.append(detection)
    return kept


def detect_furniture(
    image: Image.Image,
    furniture_classes: Sequence[str],
    config: PipelineConfig,
    device: torch.device | None = None,
) -> list[Detection]:
    device = device or best_device()
    text_labels = [[label.strip() for label in furniture_classes if label.strip()]]
    if not text_labels[0]:
        raise ValueError("At least one furniture class is required.")

    processor = AutoProcessor.from_pretrained(
        GROUNDING_DINO_MODEL, local_files_only=True
    )
    model = AutoModelForZeroShotObjectDetection.from_pretrained(
        GROUNDING_DINO_MODEL, local_files_only=True
    ).to(device)
    model.eval()

    inputs = processor(images=image, text=text_labels, return_tensors="pt").to(device)
    with torch.inference_mode():
        outputs = model(**inputs)

    result = processor.post_process_grounded_object_detection(
        outputs,
        inputs.input_ids,
        threshold=config.box_threshold,
        text_threshold=config.text_threshold,
        target_sizes=[(image.height, image.width)],
        text_labels=text_labels,
    )[0]

    labels = result.get("text_labels", result.get("labels", []))
    detections = [
        Detection(
            label=str(label),
            score=float(score),
            box=box.detach().float().cpu().numpy().astype(np.float32),
        )
        for box, score, label in zip(result["boxes"], result["scores"], labels)
    ]
    detections = _class_aware_nms(detections, config.nms_iou_threshold)
    detections = detections[: config.max_detections]

    release_memory(outputs, inputs, model, processor)
    return detections


def segment_detections(
    image: Image.Image,
    detections: list[Detection],
    device: torch.device | None = None,
) -> list[Detection]:
    if not detections:
        return detections

    device = device or best_device()
    processor = Sam2Processor.from_pretrained(SAM2_MODEL, local_files_only=True)
    model = Sam2Model.from_pretrained(SAM2_MODEL, local_files_only=True).to(device)
    model.eval()

    boxes = [[detection.box.tolist() for detection in detections]]
    inputs = processor(
        images=image,
        input_boxes=boxes,
        return_tensors="pt",
    ).to(device)
    with torch.inference_mode():
        outputs = model(**inputs, multimask_output=False)

    masks = processor.post_process_masks(
        outputs.pred_masks.cpu(),
        inputs["original_sizes"].cpu(),
    )[0]
    masks_np = masks.squeeze(1).numpy().astype(bool)
    for detection, mask in zip(detections, masks_np):
        detection.mask = mask

    release_memory(outputs, inputs, model, processor)
    return detections


def estimate_focal_length_px(
    image: Image.Image,
    config: PipelineConfig,
) -> float:
    """Estimate focal length in pixels from EXIF or assumed horizontal FOV."""
    try:
        exif = image.getexif()
        focal_35mm = exif.get(41989)  # FocalLengthIn35mmFilm
        if focal_35mm:
            return float(focal_35mm) / 36.0 * float(image.width)
    except Exception:
        pass

    fov_rad = math.radians(config.assumed_horizontal_fov_deg)
    return 0.5 * float(image.width) / math.tan(0.5 * fov_rad)


def estimate_metric_depth(
    image: Image.Image,
    config: PipelineConfig,
    device: torch.device | None = None,
) -> tuple[np.ndarray, float]:
    """Metric depth via Depth Anything V2 Indoor (meters) + FOV/EXIF focal length."""
    device = device or best_device()
    image = image.convert("RGB")
    processor = AutoImageProcessor.from_pretrained(DEPTH_ANYTHING_V2_MODEL)
    model = AutoModelForDepthEstimation.from_pretrained(DEPTH_ANYTHING_V2_MODEL)
    model.to(device)
    model.eval()

    inputs = processor(images=image, return_tensors="pt")
    inputs = {key: value.to(device) for key, value in inputs.items()}
    with torch.inference_mode():
        outputs = model(**inputs)
        predicted_depth = outputs.predicted_depth

    depth = (
        F.interpolate(
            predicted_depth.unsqueeze(1),
            size=(image.height, image.width),
            mode="bicubic",
            align_corners=False,
        )
        .squeeze()
        .detach()
        .float()
        .cpu()
        .numpy()
    )
    depth = np.clip(depth, config.depth_min_m, config.depth_max_m)
    focal_length_px = estimate_focal_length_px(image, config)
    release_memory(outputs, inputs, model, processor, predicted_depth)
    return depth, focal_length_px
