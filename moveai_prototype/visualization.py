from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
from matplotlib import colormaps
from PIL import Image, ImageDraw, ImageFont

from geometry import BOX_EDGES, ObjectMeasurement
from models import Detection


PALETTE = [
    (0, 194, 255),
    (255, 122, 0),
    (113, 224, 90),
    (255, 73, 126),
    (167, 112, 239),
    (255, 209, 64),
    (26, 188, 156),
    (231, 76, 60),
]


def render_detection_overlay(
    image: Image.Image,
    detections: list[Detection],
) -> Image.Image:
    base = np.asarray(image.convert("RGB")).astype(np.float32)
    overlay = base.copy()

    for index, detection in enumerate(detections):
        if detection.mask is None:
            continue
        color = np.asarray(PALETTE[index % len(PALETTE)], dtype=np.float32)
        mask = detection.mask
        if mask.shape != base.shape[:2]:
            mask = (
                np.asarray(
                    Image.fromarray(mask.astype(np.uint8) * 255).resize(
                        (base.shape[1], base.shape[0]),
                        Image.Resampling.NEAREST,
                    )
                )
                > 0
            )
        overlay[mask] = 0.55 * overlay[mask] + 0.45 * color

    output = Image.fromarray(np.clip(overlay, 0, 255).astype(np.uint8))
    draw = ImageDraw.Draw(output)
    font = ImageFont.load_default()
    line_width = max(2, round(max(output.size) / 450))
    for index, detection in enumerate(detections):
        color = PALETTE[index % len(PALETTE)]
        x1, y1, x2, y2 = [int(round(value)) for value in detection.box]
        draw.rectangle((x1, y1, x2, y2), outline=color, width=line_width)
        text = f"{index + 1}. {detection.label} {detection.score:.0%}"
        left, top, right, bottom = draw.textbbox((x1, y1), text, font=font)
        text_height = bottom - top + 8
        text_width = right - left + 8
        label_y = max(0, y1 - text_height)
        draw.rectangle(
            (x1, label_y, x1 + text_width, label_y + text_height),
            fill=color,
        )
        draw.text((x1 + 4, label_y + 4), text, fill="black", font=font)
    return output


def render_depth_map(depth_m: np.ndarray) -> Image.Image:
    finite = depth_m[np.isfinite(depth_m)]
    if finite.size == 0:
        return Image.fromarray(np.zeros((*depth_m.shape, 3), dtype=np.uint8))
    low, high = np.quantile(finite, [0.02, 0.98])
    normalized = np.clip((depth_m - low) / max(high - low, 1e-6), 0, 1)
    colored = colormaps["turbo_r"](normalized)[..., :3]
    return Image.fromarray((colored * 255).astype(np.uint8))


def point_cloud_figure(measurement: ObjectMeasurement) -> go.Figure:
    points = measurement.points
    colors = measurement.colors
    if len(points) > 4_000:
        indices = np.linspace(0, len(points) - 1, 4_000, dtype=int)
        points = points[indices]
        colors = colors[indices]
    color_strings = [
        f"rgb({int(red * 255)},{int(green * 255)},{int(blue * 255)})"
        for red, green, blue in colors
    ]

    figure = go.Figure()
    figure.add_trace(
        go.Scatter3d(
            x=points[:, 0],
            y=points[:, 2],
            z=points[:, 1],
            mode="markers",
            marker={"size": 2, "color": color_strings, "opacity": 0.65},
            name="Visible surface",
        )
    )
    corners = measurement.box_corners
    for start, end in BOX_EDGES:
        figure.add_trace(
            go.Scatter3d(
                x=[corners[start, 0], corners[end, 0]],
                y=[corners[start, 2], corners[end, 2]],
                z=[corners[start, 1], corners[end, 1]],
                mode="lines",
                line={"color": "#ff7a00", "width": 6},
                showlegend=False,
                hoverinfo="skip",
            )
        )
    figure.update_layout(
        height=520,
        margin={"l": 0, "r": 0, "t": 35, "b": 0},
        title=f"{measurement.label}: visible point cloud + Open3D OBB",
        scene={
            "xaxis_title": "X (m)",
            "yaxis_title": "Depth (m)",
            "zaxis_title": "Y (m)",
            "aspectmode": "data",
        },
        template="plotly_dark",
        showlegend=True,
    )
    return figure

