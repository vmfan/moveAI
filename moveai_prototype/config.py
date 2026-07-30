from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("MOVEAI_DB_PATH", PROJECT_DIR / "moveai.db"))

GROUNDING_DINO_MODEL = "IDEA-Research/grounding-dino-tiny"
SAM2_MODEL = "facebook/sam2.1-hiera-tiny"
# Indoor metric Depth Anything V2 (Hypersim fine-tune). Prefer Large on GPU.
DEPTH_ANYTHING_V2_MODEL = "depth-anything/Depth-Anything-V2-Metric-Indoor-Large-hf"

DEFAULT_FURNITURE_CLASSES = [
    "sofa",
    "bed",
    "mattress",
    "wardrobe",
    "refrigerator",
    "washing machine",
    "dining table",
    "desk",
    "cabinet",
    "chest of drawers",
    "bookshelf",
    "television",
    "armchair",
]


@dataclass(frozen=True)
class PipelineConfig:
    box_threshold: float = 0.30
    text_threshold: float = 0.25
    nms_iou_threshold: float = 0.50
    max_detections: int = 8
    max_points_per_object: int = 12_000
    depth_min_m: float = 0.20
    depth_max_m: float = 20.0
    depth_quantile_low: float = 0.05
    depth_quantile_high: float = 0.95
    use_half_precision: bool = True
    # Used when EXIF focal length is unavailable (Depth Anything V2 has no f_px head).
    assumed_horizontal_fov_deg: float = 60.0
