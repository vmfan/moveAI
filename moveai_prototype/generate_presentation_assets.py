from __future__ import annotations

import json
import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from config import PipelineConfig
from geometry import BOX_EDGES
from models import (
    best_device,
    detect_furniture,
    release_memory,
    segment_detections,
)
from pipeline import prepare_image
from visualization import PALETTE


APP_DIR = Path(__file__).resolve().parent
DEFAULT_IMAGE = (
    APP_DIR.parent / "real_world_samples" / "images" / "001_3f6e15958d41abf9.jpg"
)
OUTPUT_DIR = APP_DIR.parent.parent / "Presentations" / "presentation2_prototype_assets"
SMOKE_OUTPUT_DIR = APP_DIR / "outputs" / "smoke_test"


def render_boxes(image: Image.Image, detections) -> Image.Image:
    output = image.convert("RGB").copy()
    draw = ImageDraw.Draw(output)
    font = ImageFont.load_default()
    line_width = max(3, round(max(output.size) / 350))
    for index, detection in enumerate(detections):
        color = PALETTE[index % len(PALETTE)]
        x1, y1, x2, y2 = [int(round(value)) for value in detection.box]
        draw.rectangle((x1, y1, x2, y2), outline=color, width=line_width)
        label = f"{detection.label} {detection.score:.0%}"
        left, top, right, bottom = draw.textbbox((x1, y1), label, font=font)
        width, height = right - left + 10, bottom - top + 10
        y_text = max(0, y1 - height)
        draw.rectangle((x1, y_text, x1 + width, y_text + height), fill=color)
        draw.text((x1 + 5, y_text + 5), label, fill="black", font=font)
    return output


def render_masks(image: Image.Image, detections) -> Image.Image:
    base = np.asarray(image.convert("RGB")).astype(np.float32)
    output = base.copy()
    for index, detection in enumerate(detections):
        if detection.mask is None:
            continue
        color = np.asarray(PALETTE[index % len(PALETTE)], dtype=np.float32)
        mask = detection.mask
        output[mask] = output[mask] * 0.38 + color * 0.62
    return Image.fromarray(np.clip(output, 0, 255).astype(np.uint8))


def render_3d_box(item: dict, output_path: Path) -> None:
    length, width, height = item["width_m"], item["height_m"], item["depth_m"]
    corners = np.asarray(
        [
            [0, 0, 0],
            [length, 0, 0],
            [length, width, 0],
            [0, width, 0],
            [0, 0, height],
            [length, 0, height],
            [length, width, height],
            [0, width, height],
        ]
    )
    figure = plt.figure(figsize=(9, 6), facecolor="#071321")
    axis = figure.add_subplot(111, projection="3d")
    axis.set_facecolor("#0d1d30")
    for start, end in BOX_EDGES:
        axis.plot(
            [corners[start, 0], corners[end, 0]],
            [corners[start, 1], corners[end, 1]],
            [corners[start, 2], corners[end, 2]],
            color="#ff9d3d",
            linewidth=4,
        )
    axis.scatter(corners[:, 0], corners[:, 1], corners[:, 2], color="#37c6ff", s=34)
    axis.set_xlabel("Width (m)", color="white")
    axis.set_ylabel("Depth (m)", color="white")
    axis.set_zlabel("Height (m)", color="white")
    axis.tick_params(colors="white")
    axis.set_box_aspect((length, width, height))
    axis.set_title(
        (
            f"{item['label'].title()}: Open3D bounding box\n"
            f"{length:.2f} × {width:.2f} × {height:.2f} m"
        ),
        color="white",
        pad=18,
        fontsize=14,
    )
    figure.tight_layout()
    figure.savefig(output_path, dpi=180, bbox_inches="tight", facecolor=figure.get_facecolor())
    plt.close(figure)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    image = prepare_image(Image.open(DEFAULT_IMAGE))
    classes = ["sofa", "armchair", "desk"]
    config = PipelineConfig(max_detections=4)
    device = best_device()
    print("Running Grounding DINO...", flush=True)
    detections = detect_furniture(
        image,
        classes,
        config,
        device,
    )
    release_memory()
    print("Running SAM 2...", flush=True)
    detections = segment_detections(image, detections, device)
    release_memory()

    image.save(OUTPUT_DIR / "01_input_image.jpg", quality=94)
    render_boxes(image, detections).save(
        OUTPUT_DIR / "02_detected_objects.jpg", quality=94
    )
    render_masks(image, detections).save(
        OUTPUT_DIR / "03_pixel_masks.jpg", quality=94
    )
    shutil.copy2(
        SMOKE_OUTPUT_DIR / "depth_map.jpg",
        OUTPUT_DIR / "04_metric_depth.jpg",
    )

    smoke_inventory = json.loads(
        (SMOKE_OUTPUT_DIR / "inventory.json").read_text(encoding="utf-8")
    )
    measured_items = smoke_inventory["inventory"]
    preferred = next(
        (item for item in measured_items if "sofa" in item["label"].lower()),
        measured_items[0],
    )
    render_3d_box(preferred, OUTPUT_DIR / "05_3d_object.png")

    inventory = [
        {
            "object": item["label"],
            "confidence": round(item["score"], 3),
            "width_m": round(float(item["width_m"]), 3),
            "height_m": round(float(item["height_m"]), 3),
            "depth_m": round(float(item["depth_m"]), 3),
            "visible_volume_m3": round(item["visible_obb_volume_m3"], 3),
        }
        for item in measured_items
    ]
    total_volume = sum(item["visible_volume_m3"] for item in inventory)
    (OUTPUT_DIR / "inventory.json").write_text(
        json.dumps(
            {
                "objects": inventory,
                "total_visible_volume_m3": round(total_volume, 3),
                "measurement_note": (
                    "Single-view visible-surface lower bound; hidden surfaces excluded."
                ),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Presentation assets written to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

