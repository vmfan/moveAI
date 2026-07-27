"""Self-check for Build 5: the review-state policy, boxed-goods seeding, the
customer confirm/correct/remove loop, manual declared-item entry, and the
Inventory Review page.

Verifies review_policy.classify() against DESIGN.md SS5b's interrupt rule
(as reconciled during Build 5 planning -- geometric-soundness signals route
to staff, not the customer), persist_capture()'s now-computed review state,
inventory_sync.py's new mutation helpers, and an integration check piping a
reviewed inventory through pricing.build_quote() + db.create_quote(). Also
drives the real Streamlit Inventory Review page headlessly via AppTest,
since the environment can't run the live pipeline
(IMPLEMENTATION_ROADMAP.md's "Known environment constraints").

Run with: .venv/bin/python inventory_review_smoke_test.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

_TMP_DIR = tempfile.mkdtemp()
os.environ["MOVEAI_DB_PATH"] = str(Path(_TMP_DIR) / "app_test.db")

import numpy as np

import db
import pricing
import review_policy
from geometry import MeasurementFailure, ObjectMeasurement
from inventory_sync import (
    add_declared_item,
    apply_customer_correction,
    confirm_item,
    persist_capture,
    review_summary,
    seed_boxed_goods,
    set_boxed_goods_count,
)


PASS_COUNT = 0


def check(description: str, condition: bool) -> None:
    global PASS_COUNT
    if not condition:
        raise AssertionError(f"FAIL: {description}")
    PASS_COUNT += 1
    print(f"PASS: {description}")


VALID_INTAKE = {
    "contact_name": "Chris Ho",
    "contact_email": "chris@example.com",
    "contact_phone": "+852 9876 5432",
    "origin_address": "5 Salisbury Road, TST",
    "origin_floor": 4,
    "origin_has_lift": False,
    "origin_parking_distance_m": 10.0,
    "destination_address": "1 Harbour View St, Wan Chai",
    "destination_floor": 2,
    "destination_has_lift": True,
    "destination_parking_distance_m": 0.0,
    "room_count": 3,
    "preferred_move_date": "2026-09-01",
}


def _measurement(label: str, **overrides) -> ObjectMeasurement:
    defaults = dict(
        label=label,
        detection_score=0.85,
        width_m=1.2,
        height_m=0.8,
        depth_m=0.6,
        visible_obb_volume_m3=0.576,
        median_depth_m=2.0,
        point_count=1500,
        points=np.zeros((3, 3)),
        colors=np.zeros((3, 3)),
        box_corners=np.zeros((8, 3)),
        warning="Single-view lower bound.",
        used_axis_aligned_fallback=False,
        mask_touches_border=False,
    )
    defaults.update(overrides)
    return ObjectMeasurement(**defaults)


def test_policy_table() -> None:
    clean = review_policy.classify(
        label="sofa",
        detection_confidence=0.9,
        point_count=2000,
        used_axis_aligned_fallback=False,
        mask_touches_border=False,
        width_m=2.0,
        height_m=0.8,
        depth_m=0.9,
    )
    check("a clean measurement auto-accepts", clean.state == "auto_accept")

    border = review_policy.classify(
        label="sofa",
        detection_confidence=0.9,
        point_count=2000,
        used_axis_aligned_fallback=False,
        mask_touches_border=True,
        width_m=2.0,
        height_m=0.8,
        depth_m=0.9,
    )
    check("border truncation triggers customer_confirm", border.state == "customer_confirm")
    check("border truncation is a recorded signal", "mask_touches_border" in border.signals)

    low_conf = review_policy.classify(
        label="sofa",
        detection_confidence=0.2,
        point_count=2000,
        used_axis_aligned_fallback=False,
        mask_touches_border=False,
        width_m=2.0,
        height_m=0.8,
        depth_m=0.9,
    )
    check("low detection confidence triggers customer_confirm", low_conf.state == "customer_confirm")

    axis_aligned = review_policy.classify(
        label="sofa",
        detection_confidence=0.9,
        point_count=2000,
        used_axis_aligned_fallback=True,
        mask_touches_border=False,
        width_m=2.0,
        height_m=0.8,
        depth_m=0.9,
    )
    check(
        "axis-aligned fallback escalates to staff, not a customer prompt "
        "(customer cannot assess geometric soundness)",
        axis_aligned.state == "staff_escalate",
    )

    low_points = review_policy.classify(
        label="sofa",
        detection_confidence=0.9,
        point_count=50,
        used_axis_aligned_fallback=False,
        mask_touches_border=False,
        width_m=2.0,
        height_m=0.8,
        depth_m=0.9,
    )
    check("low point count escalates to staff", low_points.state == "staff_escalate")

    both = review_policy.classify(
        label="sofa",
        detection_confidence=0.9,
        point_count=2000,
        used_axis_aligned_fallback=True,
        mask_touches_border=True,
        width_m=2.0,
        height_m=0.8,
        depth_m=0.9,
    )
    check(
        "staff_escalate takes precedence over a simultaneous customer_confirm signal",
        both.state == "staff_escalate",
    )

    failed = review_policy.classify(
        label="sofa",
        detection_confidence=0.9,
        point_count=2000,
        used_axis_aligned_fallback=False,
        mask_touches_border=False,
        width_m=None,
        height_m=None,
        depth_m=None,
        measurement_error="Not enough valid depth pixels.",
    )
    check("a measurement failure escalates to staff", failed.state == "staff_escalate")


def test_priors_stubs_report_no_signal() -> None:
    decision = review_policy.classify(
        label="sofa",
        detection_confidence=0.9,
        point_count=2000,
        used_axis_aligned_fallback=False,
        mask_touches_border=False,
        width_m=2.0,
        height_m=0.8,
        depth_m=0.9,
    )
    check(
        "shell_ratio is None while expected_depth_m() is a no-signal stub",
        decision.shell_ratio is None,
    )
    check(
        "implausible_dimension is False while flag_implausible_dimension() is a no-signal stub",
        decision.implausible_dimension is False,
    )


def test_persist_capture_writes_computed_state(conn) -> None:
    job_id = db.create_job(conn)
    db.save_intake(conn, job_id, **VALID_INTAKE)

    border_item = _measurement("floor lamp", mask_touches_border=True)
    axis_item = _measurement("bookshelf", used_axis_aligned_fallback=True)
    clean_item = _measurement("dining table")
    failure = MeasurementFailure(
        index=1, label="cabinet", detection_score=0.4, message="Not enough valid depth pixels."
    )

    persist_capture(
        conn,
        job_id,
        measurements=[border_item, axis_item, clean_item],
        failures=[failure],
        room_label="Living room",
        source_image_name="living_room_2.jpg",
        focal_length_px=1420.0,
    )

    items = db.list_inventory_items(conn, job_id)
    by_label = {i["label"]: i for i in items}
    check(
        "border-touching item persists as customer_confirm",
        by_label["floor lamp"]["review_state"] == "customer_confirm",
    )
    check(
        "axis-aligned-fallback item persists as staff_escalate",
        by_label["bookshelf"]["review_state"] == "staff_escalate",
    )
    check(
        "a clean measurement persists as auto_accept",
        by_label["dining table"]["review_state"] == "auto_accept",
    )
    check(
        "a measurement failure still persists as staff_escalate (Build 4 behaviour unchanged)",
        by_label["cabinet"]["review_state"] == "staff_escalate",
    )
    return job_id


def test_boxed_goods(conn, job_id) -> None:
    config = db.get_active_pricing_config(conn)
    result = seed_boxed_goods(
        conn, job_id, room_count=3, volume_per_box_m3=float(config["volume_per_box_m3"])
    )
    check("seed_boxed_goods creates a line the first time", result["created"] is True)
    item = db.get_inventory_item(conn, result["item_id"])
    check("boxed-goods line seeds as customer_confirm", item["review_state"] == "customer_confirm")
    check(
        "boxed-goods seed breakdown is persisted",
        "room_baseline_boxes" in item["boxed_goods_seed_json"],
    )

    result_again = seed_boxed_goods(
        conn, job_id, room_count=3, volume_per_box_m3=float(config["volume_per_box_m3"])
    )
    check(
        "seed_boxed_goods is idempotent -- a second call doesn't create another line",
        result_again["created"] is False and result_again["item_id"] == result["item_id"],
    )
    items = db.list_inventory_items(conn, job_id)
    check(
        "exactly one boxed-goods line exists for the job",
        sum(1 for i in items if i["is_boxed_goods"]) == 1,
    )

    set_boxed_goods_count(conn, result["item_id"], 25, float(config["volume_per_box_m3"]))
    updated = db.get_inventory_item(conn, result["item_id"])
    check("customer adjustment updates the box quantity", updated["quantity"] == 25)
    check(
        "customer adjustment promotes the line out of customer_confirm",
        updated["review_state"] == "auto_accept",
    )
    check("customer adjustment marks the line customer_confirmed", updated["customer_confirmed"] == 1)


def test_correction(conn, job_id) -> None:
    items = db.list_inventory_items(conn, job_id)
    lamp = next(i for i in items if i["label"] == "floor lamp")
    check("precondition: floor lamp starts as measured/customer_confirm", lamp["measurement_basis"] == "measured")

    apply_customer_correction(conn, lamp["id"], width_m=1.5, height_m=1.8, depth_m=0.4)
    corrected = db.get_inventory_item(conn, lamp["id"])
    check("correction flips measurement_basis to declared", corrected["measurement_basis"] == "declared")
    check(
        "correction recomputes unit_volume_m3",
        abs(corrected["unit_volume_m3"] - (1.5 * 1.8 * 0.4)) < 1e-9,
    )
    check(
        "correction preserves the original dimensions in provenance",
        corrected["provenance_json"]["customer_override"]["previous_measurement_basis"] == "measured",
    )
    check("correction sets customer_confirmed", corrected["customer_confirmed"] == 1)
    check(
        "correction promotes out of customer_confirm",
        corrected["review_state"] == "auto_accept",
    )


def test_confirm_does_not_clear_escalation(conn, job_id) -> None:
    items = db.list_inventory_items(conn, job_id)
    cabinet = next(i for i in items if i["label"] == "cabinet")
    check("precondition: cabinet is staff_escalate", cabinet["review_state"] == "staff_escalate")

    confirm_item(conn, cabinet["id"])
    after = db.get_inventory_item(conn, cabinet["id"])
    check(
        "confirming a staff-escalated item does not clear the escalation",
        after["review_state"] == "staff_escalate" and after["customer_confirmed"] == 1,
    )


def test_manual_add(conn, job_id) -> None:
    item_id = add_declared_item(
        conn,
        job_id,
        label="Piano",
        room_label="Living room",
        quantity=1,
        width_m=1.5,
        height_m=1.1,
        depth_m=0.6,
    )
    item = db.get_inventory_item(conn, item_id)
    check("manually-added item is declared", item["measurement_basis"] == "declared")
    check("manually-added item auto-accepts", item["review_state"] == "auto_accept")
    check("manually-added item is pre-confirmed", item["customer_confirmed"] == 1)


def test_integration_through_quote(conn, job_id) -> None:
    intake = db.get_intake(conn, job_id)
    config = db.get_active_pricing_config(conn)
    items = db.list_inventory_items(conn, job_id)
    quote = pricing.build_quote(items, intake, config)

    check("the escalated cabinet is reported, not silently dropped", len(quote.escalated_item_ids) >= 1)

    lamp_line = next(
        (l for l in quote.lines if any(i["id"] == l.inventory_item_id and i["label"] == "floor lamp" for i in items)),
        None,
    )
    check("the corrected item produces a quote line", lamp_line is not None)
    check("the corrected item's line carries measurement_basis='declared'", lamp_line.measurement_basis == "declared")

    quote_id = db.create_quote(
        conn,
        job_id,
        pricing_config_id=config["id"],
        **{
            k: v
            for k, v in pricing.quote_to_db_kwargs(quote, pricing_config_id=config["id"]).items()
            if k != "pricing_config_id"
        },
    )
    lines = db.get_quote_lines(conn, quote_id)
    lamp_db_line = next(l for l in lines if l["inventory_item_id"] == lamp_line.inventory_item_id)
    check(
        "the corrected (declared) item's quote_line is surcharge-eligible",
        lamp_db_line["surcharge_eligible"] == 1,
    )

    boxed_item = next(i for i in items if i["is_boxed_goods"])
    boxed_line = next(l for l in lines if l["inventory_item_id"] == boxed_item["id"])
    expected_labour = float(config["boxed_goods_labour_multiplier"])
    check(
        "boxed-goods line's price reflects the boxed-goods labour multiplier",
        boxed_line["price_component"]
        > boxed_line["volume_m3"] * float(config["price_per_m3"]) * quote.access_multiplier * 0.99,
    )
    _ = expected_labour


def test_review_page_via_apptest() -> None:
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file("pages/2_Inventory_Review.py")
    at.run()
    check("Inventory Review page renders with no active job", not at.exception)

    conn = db.connect()
    job_id = db.create_job(conn)
    db.save_intake(conn, job_id, **VALID_INTAKE)
    persist_capture(
        conn,
        job_id,
        measurements=[_measurement("armchair", mask_touches_border=True)],
        failures=[],
        room_label="Living room",
        source_image_name="apptest_capture.jpg",
        focal_length_px=1400.0,
    )

    at2 = AppTest.from_file("pages/2_Inventory_Review.py")
    at2.session_state["job_id"] = job_id
    at2.run()
    check("Inventory Review page renders with a seeded job", not at2.exception)

    confirm_buttons = [b for b in at2.button if b.label.startswith("✅ Confirm")]
    check("a Confirm button is rendered for the flagged item", len(confirm_buttons) == 1)
    confirm_buttons[0].click().run()
    check("clicking Confirm renders no exception", not at2.exception)

    item = next(
        i for i in db.list_inventory_items(conn, job_id) if i["label"] == "armchair"
    )
    check("clicking Confirm actually wrote the row", item["review_state"] == "auto_accept")


def main() -> None:
    conn = db.connect()
    db.initialize(conn)

    test_policy_table()
    test_priors_stubs_report_no_signal()
    job_id = test_persist_capture_writes_computed_state(conn)
    test_boxed_goods(conn, job_id)
    test_correction(conn, job_id)
    test_confirm_does_not_clear_escalation(conn, job_id)
    test_manual_add(conn, job_id)
    test_integration_through_quote(conn, job_id)
    test_review_page_via_apptest()

    print(f"\n{PASS_COUNT} checks passed.")


if __name__ == "__main__":
    sys.exit(main())
