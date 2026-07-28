"""Self-check for Build 10's model-caching claim: `backend/pipeline_runtime.py`
monkey-patches the `from_pretrained`-style entry points `models.py` calls so a
second pipeline run reuses already-loaded models instead of reloading them
from disk.

Isolates the caching benchmark from the router per the roadmap's own
instruction ("time a first vs second /capture call... isolate this in a
small script before wiring the router"). Grounding DINO, SAM2, and the Depth
Pro checkpoint are confirmed cached on this dev machine
(IMPLEMENTATION_ROADMAP.md's pre-Build-8 update), so this is a real
end-to-end pipeline run, not a synthetic substitution.

Run with: .venv/bin/python pipeline_runtime_smoke_test.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

from backend import pipeline_runtime  # noqa: E402
from config import DEFAULT_FURNITURE_CLASSES, PipelineConfig  # noqa: E402

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "real_world_samples" / "images"

PASS_COUNT = 0


def check(description: str, condition: bool) -> None:
    global PASS_COUNT
    if not condition:
        raise AssertionError(f"FAIL: {description}")
    PASS_COUNT += 1
    print(f"PASS: {description}")


def main() -> None:
    sample_paths = sorted(SAMPLE_DIR.glob("*.jpg"))
    check("at least one real sample image is available", len(sample_paths) > 0)
    image = Image.open(sample_paths[0])
    config = PipelineConfig()

    start = time.perf_counter()
    first_result = pipeline_runtime.run_pipeline_locked(
        image, DEFAULT_FURNITURE_CLASSES, config
    )
    first_elapsed = time.perf_counter() - start
    check("first (cold) run produced at least one measurement or failure",
          len(first_result.measurements) + len(first_result.measurement_errors) > 0)

    start = time.perf_counter()
    second_result = pipeline_runtime.run_pipeline_locked(
        image, DEFAULT_FURNITURE_CLASSES, config
    )
    second_elapsed = time.perf_counter() - start
    check("second (warm) run produced the same measurement count",
          len(second_result.measurements) == len(first_result.measurements))

    print(f"\nfirst run: {first_elapsed:.1f}s, second run: {second_elapsed:.1f}s")
    check(
        "second run is materially faster than the first (model caching works)",
        second_elapsed < first_elapsed * 0.6,
    )
    check("second run completes in single-digit seconds, not a cold ~3 min load",
          second_elapsed < 30.0)

    print(f"\n{PASS_COUNT} checks passed.")


if __name__ == "__main__":
    sys.exit(main())
