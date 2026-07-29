"""Self-check for the multi-image capture build: per-image artifact storage
(`backend/serialization.py`), additive DB rows across distinct
`source_image_name`s (`inventory_sync.persist_capture()`, unchanged), and
the cross-image dedup + room-labeling pass (`backend/dedup.py`) against a
mocked `reasoning_client` -- no live network call, so this stays
deterministic and doesn't depend on the HKUST endpoint being reachable.

Run with: .venv/bin/python dedup_smoke_test.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

_TMP_DIR = tempfile.mkdtemp()
os.environ["MOVEAI_DB_PATH"] = str(Path(_TMP_DIR) / "app_test.db")

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

import numpy as np
from PIL import Image

import db  # noqa: E402
import inventory_sync  # noqa: E402
from backend import dedup, reasoning_client, serialization  # noqa: E402
from geometry import ObjectMeasurement  # noqa: E402
from pipeline import PipelineResult  # noqa: E402

PASS_COUNT = 0


def check(description: str, condition: bool) -> None:
    global PASS_COUNT
    if not condition:
        raise AssertionError(f"FAIL: {description}")
    PASS_COUNT += 1
    print(f"PASS: {description}")


def make_measurement(label: str, score: float) -> ObjectMeasurement:
    return ObjectMeasurement(
        label=label,
        detection_score=score,
        width_m=1.0,
        height_m=0.8,
        depth_m=0.6,
        visible_obb_volume_m3=0.48,
        median_depth_m=2.0,
        point_count=500,
        points=np.zeros((1, 3)),
        colors=np.zeros((1, 3)),
        box_corners=np.zeros((8, 3)),
        warning="",
        used_axis_aligned_fallback=False,
        mask_touches_border=False,
    )


def make_result(measurements: list[ObjectMeasurement]) -> PipelineResult:
    return PipelineResult(
        image=Image.new("RGB", (64, 64)),
        detections=[],
        depth_m=np.ones((64, 64), dtype=np.float32),
        focal_length_px=1000.0,
        measurements=measurements,
        measurement_errors=[],
        timings_s={"total": 1.0},
    )


def main() -> None:
    conn = db.connect()
    db.initialize(conn)
    job_id = db.create_job(conn)

    # -- serialization.py: per-image storage, no overwrite -----------------
    result_a = make_result([make_measurement("Sofa", 0.9)])
    result_b = make_result([make_measurement("Sofa", 0.8), make_measurement("Chair", 0.7)])

    serialization.store_result(job_id, "a.jpg", result_a)
    serialization.store_result(job_id, "b.jpg", result_b)

    check(
        "storing a second image's result doesn't overwrite the first",
        serialization.get_result(job_id, "a.jpg") is result_a,
    )
    check(
        "second image's result is retrievable under its own key",
        serialization.get_result(job_id, "b.jpg") is result_b,
    )
    all_results = serialization.list_results_for_job(job_id)
    check("list_results_for_job returns both stored images", set(all_results) == {"a.jpg", "b.jpg"})

    combined = serialization.combined_inventory_json(all_results)
    check(
        "combined_inventory_json tags each item with its source image",
        {item["source_image_name"] for item in combined["items"]} == {"a.jpg", "b.jpg"},
    )
    check("combined_inventory_json merges item counts across images", len(combined["items"]) == 3)

    # -- persist_capture: additive rows across distinct source_image_name --
    summary_a = inventory_sync.persist_capture(
        conn,
        job_id,
        measurements=result_a.measurements,
        failures=[],
        room_label=None,
        source_image_name="a.jpg",
        focal_length_px=result_a.focal_length_px,
    )
    summary_b = inventory_sync.persist_capture(
        conn,
        job_id,
        measurements=result_b.measurements,
        failures=[],
        room_label=None,
        source_image_name="b.jpg",
        focal_length_px=result_b.focal_length_px,
    )
    all_items = db.list_inventory_items(conn, job_id)
    check(
        "capturing a second distinct image adds rows rather than replacing the first",
        len(all_items) == 3,
    )
    check(
        "rows from both images are present, tagged by source_image_name",
        {item["source_image_name"] for item in all_items} == {"a.jpg", "b.jpg"},
    )

    # -- dedup.py: merge a genuine duplicate, mocked reasoning_client ------
    captures = [
        dedup.CaptureBatchImage(
            image_name="a.jpg",
            result=result_a,
            measured_item_ids=summary_a["measured_item_ids"],
            room_label=None,
        ),
        dedup.CaptureBatchImage(
            image_name="b.jpg",
            result=result_b,
            measured_item_ids=summary_b["measured_item_ids"],
            room_label=None,
        ),
    ]

    original_ask = reasoning_client.ask_vision_json
    reasoning_client.ask_vision_json = lambda **kwargs: {
        "duplicate_groups": [
            [
                {"image_name": "a.jpg", "item_index": 1},
                {"image_name": "b.jpg", "item_index": 1},
            ]
        ],
        "room_labels": {"a.jpg": "Living room", "b.jpg": "Living room"},
    }
    try:
        outcome = dedup.run_dedup_and_labeling(conn, job_id, captures)
    finally:
        reasoning_client.ask_vision_json = original_ask

    check("one duplicate group merged", len(outcome["duplicates_removed"]) == 1)
    kept_id = outcome["duplicates_removed"][0]["kept_item_id"]
    removed_ids = outcome["duplicates_removed"][0]["removed_item_ids"]
    check(
        "the higher-confidence item (a.jpg's Sofa, 0.9) was kept",
        kept_id == summary_a["measured_item_ids"][0],
    )
    check(
        "the lower-confidence duplicate (b.jpg's Sofa, 0.8) was removed",
        removed_ids == [summary_b["measured_item_ids"][0]],
    )

    remaining = db.list_inventory_items(conn, job_id)
    check("the duplicate row is actually gone from the DB", len(remaining) == 2)
    check(
        "the non-duplicate Chair from b.jpg survived untouched",
        any(item["label"] == "Chair" for item in remaining),
    )

    kept_item = db.get_inventory_item(conn, kept_id)
    frames = (kept_item["provenance_json"] or {}).get("frames", [])
    check(
        "the kept item's provenance folds in both source images",
        {f.get("image_name") for f in frames} >= {"a.jpg", "b.jpg"},
    )
    check(
        "room labels were applied to surviving items",
        all(item["room_label"] == "Living room" for item in db.list_inventory_items(conn, job_id)),
    )

    # -- dedup.py: two genuinely different items must NOT be merged --------
    job_id_2 = db.create_job(conn)
    result_c = make_result([make_measurement("Sofa", 0.9)])
    result_d = make_result([make_measurement("Bookshelf", 0.9)])
    summary_c = inventory_sync.persist_capture(
        conn, job_id_2, measurements=result_c.measurements, failures=[],
        room_label=None, source_image_name="c.jpg", focal_length_px=1000.0,
    )
    summary_d = inventory_sync.persist_capture(
        conn, job_id_2, measurements=result_d.measurements, failures=[],
        room_label=None, source_image_name="d.jpg", focal_length_px=1000.0,
    )
    captures_2 = [
        dedup.CaptureBatchImage("c.jpg", result_c, summary_c["measured_item_ids"], None),
        dedup.CaptureBatchImage("d.jpg", result_d, summary_d["measured_item_ids"], None),
    ]
    reasoning_client.ask_vision_json = lambda **kwargs: {"duplicate_groups": [], "room_labels": {}}
    try:
        outcome_2 = dedup.run_dedup_and_labeling(conn, job_id_2, captures_2)
    finally:
        reasoning_client.ask_vision_json = original_ask
    check("no merges when the model reports no duplicate groups", outcome_2["duplicates_removed"] == [])
    check(
        "both genuinely different items survive",
        len(db.list_inventory_items(conn, job_id_2)) == 2,
    )

    # -- graceful degradation: model call fails, capture stays intact ------
    def _raise(**kwargs):
        raise reasoning_client.ReasoningClientError("simulated network failure")

    reasoning_client.ask_vision_json = _raise
    threw = False
    try:
        dedup.run_dedup_and_labeling(conn, job_id_2, captures_2)
    except reasoning_client.ReasoningClientError:
        threw = True
    finally:
        reasoning_client.ask_vision_json = original_ask
    check("a reasoning-client failure raises ReasoningClientError, not a crash", threw)
    check(
        "a failed dedup pass leaves prior DB rows untouched (no rollback needed)",
        len(db.list_inventory_items(conn, job_id_2)) == 2,
    )

    print(f"\n{PASS_COUNT}/{PASS_COUNT} checks passed")


if __name__ == "__main__":
    main()
