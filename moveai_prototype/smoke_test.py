from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image

from config import DEFAULT_FURNITURE_CLASSES, PipelineConfig
from pipeline import run_pipeline
from visualization import render_depth_map, render_detection_overlay


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full MoveAI CV pipeline.")
    parser.add_argument("image", type=Path)
    parser.add_argument("--output", type=Path, default=Path("outputs/smoke_test"))
    parser.add_argument("--max-detections", type=int, default=4)
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    image = Image.open(args.image)
    config = PipelineConfig(max_detections=args.max_detections)

    def progress(message: str, value: float) -> None:
        print(f"[{value:>5.0%}] {message}", flush=True)

    result = run_pipeline(
        image,
        DEFAULT_FURNITURE_CLASSES,
        config,
        progress,
    )
    render_detection_overlay(result.image, result.detections).save(
        args.output / "detections_and_masks.jpg"
    )
    render_depth_map(result.depth_m).save(args.output / "depth_map.jpg")

    inventory = []
    for measurement in result.measurements:
        inventory.append(
            {
                "label": measurement.label,
                "score": measurement.detection_score,
                "obb_edges_m": measurement.dimensions_m.tolist(),
                "visible_obb_volume_m3": measurement.visible_obb_volume_m3,
                "median_depth_m": measurement.median_depth_m,
                "warning": measurement.warning,
            }
        )
    (args.output / "inventory.json").write_text(
        json.dumps(
            {
                "focal_length_px": result.focal_length_px,
                "timings_s": result.timings_s,
                "measurement_errors": result.measurement_errors,
                "inventory": inventory,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote outputs to {args.output.resolve()}")


if __name__ == "__main__":
    main()

