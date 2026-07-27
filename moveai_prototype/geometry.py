from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import open3d as o3d
from PIL import Image

from config import PipelineConfig
from models import Detection


BOX_EDGES = [
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 0),
    (4, 5),
    (5, 6),
    (6, 7),
    (7, 4),
    (0, 4),
    (1, 5),
    (2, 6),
    (3, 7),
]


@dataclass
class ObjectMeasurement:
    label: str
    detection_score: float
    width_m: float
    height_m: float
    depth_m: float
    visible_obb_volume_m3: float
    median_depth_m: float
    point_count: int
    points: np.ndarray
    colors: np.ndarray
    box_corners: np.ndarray
    warning: str
    used_axis_aligned_fallback: bool
    mask_touches_border: bool


@dataclass(frozen=True)
class MeasurementFailure:
    """A detection that failed to measure -- DESIGN.md SS5b: "a failed
    measurement is never silently dropped", so this carries enough to
    become a staff-escalated inventory row rather than a log line.
    """

    index: int
    label: str
    detection_score: float
    message: str

    @property
    def display(self) -> str:
        return f"{self.index}. {self.label}: {self.message}"


def _mask_touches_border(mask: np.ndarray) -> bool:
    """DESIGN.md SS5b border-truncation signal: the mask touches an image
    edge, so the object is likely cropped rather than fully captured.
    """
    return bool(
        mask[0, :].any()
        or mask[-1, :].any()
        or mask[:, 0].any()
        or mask[:, -1].any()
    )


def _resize_mask(mask: np.ndarray, target_shape: tuple[int, int]) -> np.ndarray:
    if mask.shape == target_shape:
        return mask.astype(bool)
    resized = Image.fromarray(mask.astype(np.uint8) * 255).resize(
        (target_shape[1], target_shape[0]),
        Image.Resampling.NEAREST,
    )
    return np.asarray(resized) > 0


def _masked_point_cloud(
    image_rgb: np.ndarray,
    depth_m: np.ndarray,
    mask: np.ndarray,
    focal_length_px: float,
    config: PipelineConfig,
) -> tuple[np.ndarray, np.ndarray]:
    height, width = depth_m.shape
    mask = _resize_mask(mask, depth_m.shape)
    valid = (
        mask
        & np.isfinite(depth_m)
        & (depth_m >= config.depth_min_m)
        & (depth_m <= config.depth_max_m)
    )
    depths = depth_m[valid]
    if depths.size < 20:
        raise ValueError("Not enough valid depth pixels inside the object mask.")

    low, high = np.quantile(
        depths,
        [config.depth_quantile_low, config.depth_quantile_high],
    )
    valid &= (depth_m >= low) & (depth_m <= high)
    rows, cols = np.nonzero(valid)
    z = depth_m[rows, cols]

    if z.size > config.max_points_per_object:
        indices = np.linspace(
            0,
            z.size - 1,
            config.max_points_per_object,
            dtype=int,
        )
        rows, cols, z = rows[indices], cols[indices], z[indices]

    center_x = (width - 1) / 2.0
    center_y = (height - 1) / 2.0
    x = (cols - center_x) * z / focal_length_px
    y = -(rows - center_y) * z / focal_length_px
    points = np.column_stack((x, y, z)).astype(np.float64)

    image_for_depth = np.asarray(
        Image.fromarray(image_rgb).resize(
            (width, height),
            Image.Resampling.BILINEAR,
        )
    )
    colors = image_for_depth[rows, cols].astype(np.float64) / 255.0
    return points, colors


def _named_dimensions(
    extents: np.ndarray, rotation: np.ndarray
) -> tuple[float, float, float]:
    """Assign fitted-box extents to width/height/depth by how each local
    axis (a column of `rotation`) aligns with the camera-frame axes.

    Depth is whichever local axis points most toward the camera (+z);
    height is whichever remaining axis points most toward up (+y); width
    is what's left. An identity rotation (axis-aligned fallback) resolves
    to extents[0]=width, extents[1]=height, extents[2]=depth, matching
    Open3D's x/y/z ordering for that case.
    """
    alignment = np.abs(rotation)
    remaining = [0, 1, 2]
    depth_axis = max(remaining, key=lambda i: alignment[2, i])
    remaining.remove(depth_axis)
    height_axis = max(remaining, key=lambda i: alignment[1, i])
    remaining.remove(height_axis)
    width_axis = remaining[0]
    return (
        float(extents[width_axis]),
        float(extents[height_axis]),
        float(extents[depth_axis]),
    )


def measure_detection(
    image: Image.Image,
    depth_m: np.ndarray,
    focal_length_px: float,
    detection: Detection,
    config: PipelineConfig,
) -> ObjectMeasurement:
    if detection.mask is None:
        raise ValueError("SAM 2 mask is missing for this detection.")

    image_rgb = np.asarray(image.convert("RGB"))
    points, colors = _masked_point_cloud(
        image_rgb,
        depth_m,
        detection.mask,
        focal_length_px,
        config,
    )

    point_cloud = o3d.geometry.PointCloud()
    point_cloud.points = o3d.utility.Vector3dVector(points)
    point_cloud.colors = o3d.utility.Vector3dVector(colors)
    if len(points) >= 50:
        point_cloud, _ = point_cloud.remove_statistical_outlier(
            nb_neighbors=min(20, len(points) - 1),
            std_ratio=2.0,
        )

    clean_points = np.asarray(point_cloud.points)
    clean_colors = np.asarray(point_cloud.colors)
    if len(clean_points) < 10:
        clean_points, clean_colors = points, colors
        point_cloud.points = o3d.utility.Vector3dVector(clean_points)

    warning = (
        "Single-view lower bound: hidden surfaces are not reconstructed, "
        "so transport volume may be underestimated."
    )
    used_axis_aligned_fallback = False
    try:
        box = point_cloud.get_minimal_oriented_bounding_box(robust=True)
        rotation = np.asarray(box.R, dtype=float)
    except RuntimeError:
        box = point_cloud.get_axis_aligned_bounding_box()
        rotation = np.eye(3)
        used_axis_aligned_fallback = True
        warning = "Axis-aligned fallback used. " + warning

    extents = np.asarray(box.extent, dtype=float)
    width_m, height_m, depth_m = _named_dimensions(extents, rotation)
    corners = np.asarray(box.get_box_points(), dtype=float)
    volume = float(np.prod(np.maximum(extents, 0.0)))

    return ObjectMeasurement(
        label=detection.label,
        detection_score=detection.score,
        width_m=width_m,
        height_m=height_m,
        depth_m=depth_m,
        visible_obb_volume_m3=volume,
        median_depth_m=float(np.median(clean_points[:, 2])),
        point_count=len(clean_points),
        points=clean_points,
        colors=clean_colors,
        box_corners=corners,
        warning=warning,
        used_axis_aligned_fallback=used_axis_aligned_fallback,
        mask_touches_border=_mask_touches_border(detection.mask),
    )


def measure_all(
    image: Image.Image,
    depth_m: np.ndarray,
    focal_length_px: float,
    detections: list[Detection],
    config: PipelineConfig,
) -> tuple[list[ObjectMeasurement], list[MeasurementFailure]]:
    measurements: list[ObjectMeasurement] = []
    errors: list[MeasurementFailure] = []
    for index, detection in enumerate(detections, start=1):
        try:
            measurements.append(
                measure_detection(
                    image,
                    depth_m,
                    focal_length_px,
                    detection,
                    config,
                )
            )
        except (ValueError, RuntimeError) as exc:
            errors.append(
                MeasurementFailure(
                    index=index,
                    label=detection.label,
                    detection_score=detection.score,
                    message=str(exc),
                )
            )
    return measurements, errors

