"""Self-check for Build 6: quote versioning (staleness-gated, not per-load),
surcharge-eligibility staying keyed on measurement_basis all the way to the
booking-gate reason list, and the Quote page.

Verifies quote_sync.quote_matches()'s rerun-idempotency guarantee, that an
unconfirmed customer_confirm item never becomes surcharge-eligible (Build 6's
resolved product decision: an unchecked flag costs a staff review, not
money -- see IMPLEMENTATION_ROADMAP.md Build 6 / DESIGN.md SS5c), and drives
the real Streamlit Quote page headlessly via AppTest, since the environment
can't run the live pipeline (IMPLEMENTATION_ROADMAP.md's "Known environment
constraints").

Run with: .venv/bin/python quote_smoke_test.py
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
from geometry import ObjectMeasurement
from inventory_sync import (
    add_declared_item,
    apply_customer_correction,
    persist_capture,
    seed_boxed_goods,
)
from quote_sync import (
    declared_volume_m3,
    persist_quote,
    quote_matches,
    quote_view_rows,
    staff_review_reasons,
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


def _setup_job(conn) -> int:
    job_id = db.create_job(conn)
    db.save_intake(conn, job_id, **VALID_INTAKE)
    persist_capture(
        conn,
        job_id,
        measurements=[_measurement("dining table"), _measurement("armchair", mask_touches_border=True)],
        failures=[],
        room_label="Living room",
        source_image_name="living_room_1.jpg",
        focal_length_px=1400.0,
    )
    config = db.get_active_pricing_config(conn)
    seed_boxed_goods(
        conn, job_id, room_count=3, volume_per_box_m3=float(config["volume_per_box_m3"])
    )
    return job_id


def test_v1_auto_persists_and_rerun_is_idempotent(conn) -> int:
    job_id = _setup_job(conn)
    intake = db.get_intake(conn, job_id)
    config = db.get_active_pricing_config(conn)
    items = db.list_inventory_items(conn, job_id)

    quote = pricing.build_quote(items, intake, config)
    stored_before = db.get_active_quote(conn, job_id)
    check("no quote exists before the first visit", stored_before is None)

    persist_quote(conn, job_id, quote, pricing_config_id=config["id"])
    v1 = db.get_active_quote(conn, job_id)
    check("v1 auto-persists", v1["version"] == 1)
    check("job status advances to quoted", db.get_job(conn, job_id)["status"] == "quoted")

    # Simulate a rerun: recompute from unchanged inventory and confirm the
    # staleness gate says nothing changed, so the page would not re-persist.
    items_again = db.list_inventory_items(conn, job_id)
    quote_again = pricing.build_quote(items_again, intake, config)
    stored_lines = db.get_quote_lines(conn, v1["id"])
    check(
        "recomputing unchanged inventory matches the stored quote (rerun-idempotency)",
        quote_matches(v1, stored_lines, quote_again),
    )

    quotes = db.list_quotes(conn, job_id)
    check("still only one quote version exists", len(quotes) == 1)

    return job_id


def test_inventory_change_triggers_regeneration(conn, job_id) -> None:
    intake = db.get_intake(conn, job_id)
    config = db.get_active_pricing_config(conn)
    v1 = db.get_active_quote(conn, job_id)
    v1_lines = db.get_quote_lines(conn, v1["id"])
    v1_total_price = v1["total_price"]

    add_declared_item(
        conn,
        job_id,
        label="Piano",
        room_label="Living room",
        quantity=1,
        width_m=1.5,
        height_m=1.1,
        depth_m=0.6,
    )

    items = db.list_inventory_items(conn, job_id)
    fresh_quote = pricing.build_quote(items, intake, config)
    check(
        "adding an item makes the fresh quote diverge from the stored one",
        not quote_matches(v1, v1_lines, fresh_quote),
    )

    persist_quote(conn, job_id, fresh_quote, pricing_config_id=config["id"])
    v2 = db.get_active_quote(conn, job_id)
    check("regeneration creates v2", v2["version"] == 2)

    quotes = db.list_quotes(conn, job_id)
    superseded_v1 = next(q for q in quotes if q["version"] == 1)
    check("v1 is flagged superseded", superseded_v1["is_superseded"] == 1)
    check(
        "v1's stored total_price is unmutated",
        abs(superseded_v1["total_price"] - v1_total_price) < 1e-9,
    )


def test_unconfirmed_flag_costs_no_money(conn, job_id) -> None:
    items = db.list_inventory_items(conn, job_id)
    armchair = next(i for i in items if i["label"] == "armchair")
    check(
        "precondition: armchair is an unconfirmed customer_confirm item",
        armchair["review_state"] == "customer_confirm",
    )
    check(
        "precondition: armchair is still measurement_basis=measured (never touched)",
        armchair["measurement_basis"] == "measured",
    )

    intake = db.get_intake(conn, job_id)
    config = db.get_active_pricing_config(conn)
    quote = pricing.build_quote(items, intake, config)
    rows = quote_view_rows(items, quote)
    armchair_row = next(r for r in rows if r["label"] == "armchair")
    check(
        "an unconfirmed measured item is never surcharge-eligible",
        armchair_row["surcharge_eligible"] is False,
    )

    quote_id = persist_quote(conn, job_id, quote, pricing_config_id=config["id"])
    lines = db.get_quote_lines(conn, quote_id)
    armchair_line = next(l for l in lines if l["inventory_item_id"] == armchair["id"])
    check(
        "db.py's CHECK agrees: armchair's quote_line is not surcharge_eligible",
        armchair_line["surcharge_eligible"] == 0,
    )

    piano = next(i for i in items if i["label"] == "Piano")
    piano_line = next(l for l in lines if l["inventory_item_id"] == piano["id"])
    check(
        "a manually-added declared item is surcharge-eligible",
        piano_line["surcharge_eligible"] == 1,
    )

    reasons = staff_review_reasons(items, quote)
    check(
        "the unconfirmed armchair drives a staff-review reason, not a surcharge",
        any("armchair" in r for r in reasons),
    )


def test_correction_becomes_surcharge_eligible(conn, job_id) -> None:
    items = db.list_inventory_items(conn, job_id)
    armchair = next(i for i in items if i["label"] == "armchair")
    apply_customer_correction(conn, armchair["id"], width_m=1.0, height_m=0.9, depth_m=0.9)

    items = db.list_inventory_items(conn, job_id)
    intake = db.get_intake(conn, job_id)
    config = db.get_active_pricing_config(conn)
    quote = pricing.build_quote(items, intake, config)
    rows = quote_view_rows(items, quote)
    armchair_row = next(r for r in rows if r["label"] == "armchair")
    check(
        "a customer-corrected item becomes surcharge-eligible",
        armchair_row["surcharge_eligible"] is True,
    )

    reasons = staff_review_reasons(items, quote)
    check(
        "correcting the armchair clears its staff-review reason",
        not any("armchair" in r for r in reasons),
    )


def test_staff_review_reasons_cover_escalated_and_unmeasured(conn) -> None:
    job_id = db.create_job(conn)
    db.save_intake(conn, job_id, **VALID_INTAKE)
    db.add_inventory_item(
        conn,
        job_id,
        label="cabinet",
        measurement_basis="measured",
        measurement_error="Not enough valid depth pixels.",
        review_state="staff_escalate",
        review_reason="Measurement failed.",
    )
    # An item with a resolvable review state but no dimensions/volume at all.
    db.add_inventory_item(
        conn,
        job_id,
        label="mystery item",
        measurement_basis="prior_assisted",
        review_state="auto_accept",
    )
    intake = db.get_intake(conn, job_id)
    config = db.get_active_pricing_config(conn)
    items = db.list_inventory_items(conn, job_id)
    quote = pricing.build_quote(items, intake, config)

    check("the escalated cabinet is reported", len(quote.escalated_item_ids) == 1)
    check("the unmeasured mystery item is reported", len(quote.unmeasured_item_ids) == 1)

    reasons = staff_review_reasons(items, quote)
    check(
        "staff_review_reasons flags the escalated item",
        any("escalated" in r for r in reasons),
    )
    check(
        "staff_review_reasons flags the unmeasured item",
        any("no resolvable volume" in r for r in reasons),
    )


def test_staff_review_reasons_flags_oversize_truck() -> None:
    huge_item = {
        "id": 1,
        "review_state": "auto_accept",
        "unit_volume_m3": 500.0,
        "quantity": 1,
        "width_m": 10.0,
        "height_m": 2.0,
        "depth_m": 2.0,
        "measurement_basis": "measured",
    }
    config = db.get_active_pricing_config(db.connect())
    intake = VALID_INTAKE
    quote = pricing.build_quote([huge_item], intake, config)
    reasons = staff_review_reasons([huge_item], quote)
    check(
        "an oversize item drives a staff-review reason",
        any("oversize" in r.lower() for r in reasons),
    )


def test_boxed_goods_included_without_visiting_review(conn) -> None:
    job_id = db.create_job(conn)
    db.save_intake(conn, job_id, **VALID_INTAKE)
    persist_capture(
        conn,
        job_id,
        measurements=[_measurement("dining table")],
        failures=[],
        room_label="Living room",
        source_image_name="skip_review.jpg",
        focal_length_px=1400.0,
    )
    config = db.get_active_pricing_config(conn)
    # Simulate the Quote page's own idempotent seed call, skipping the
    # review page entirely.
    seed_boxed_goods(
        conn, job_id, room_count=3, volume_per_box_m3=float(config["volume_per_box_m3"])
    )
    items = db.list_inventory_items(conn, job_id)
    check(
        "boxed goods are present even without a review-page visit",
        any(i["is_boxed_goods"] for i in items),
    )


def test_declared_volume_and_surcharge_tiers(conn, job_id) -> None:
    intake = db.get_intake(conn, job_id)
    config = db.get_active_pricing_config(conn)
    items = db.list_inventory_items(conn, job_id)
    quote = pricing.build_quote(items, intake, config)

    declared_m3 = declared_volume_m3(quote)
    check("declared_volume_m3 is positive with declared lines present", declared_m3 > 0)

    outcome_small = pricing.declared_excess_surcharge(
        declared_m3, declared_m3 * 1.21, quote.total_price
    )
    check("a >20% excess matches the 20% tier", abs(outcome_small.surcharge_fraction - 0.20) < 1e-9)

    outcome_large = pricing.declared_excess_surcharge(
        declared_m3, declared_m3 * 1.51, quote.total_price
    )
    check("a >50% excess matches the 50% tier", abs(outcome_large.surcharge_fraction - 0.50) < 1e-9)


def test_quote_page_via_apptest() -> None:
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file("pages/3_Quote.py")
    at.run()
    check("Quote page renders with no active job", not at.exception)

    conn = db.connect()
    job_id = db.create_job(conn)
    db.save_intake(conn, job_id, **VALID_INTAKE)
    persist_capture(
        conn,
        job_id,
        measurements=[_measurement("dining table")],
        failures=[],
        room_label="Living room",
        source_image_name="apptest_quote.jpg",
        focal_length_px=1400.0,
    )

    at2 = AppTest.from_file("pages/3_Quote.py")
    at2.session_state["job_id"] = job_id
    at2.run()
    check("Quote page renders with a seeded job", not at2.exception)
    check("visiting the page auto-persists v1", db.get_active_quote(conn, job_id) is not None)

    # Trigger a change and confirm a Regenerate button appears and works.
    add_declared_item(
        conn,
        job_id,
        label="Extra chair",
        room_label="Living room",
        quantity=1,
        width_m=0.5,
        height_m=0.9,
        depth_m=0.5,
    )
    at3 = AppTest.from_file("pages/3_Quote.py")
    at3.session_state["job_id"] = job_id
    at3.run()
    check("Quote page renders after inventory changed", not at3.exception)
    regenerate_buttons = [b for b in at3.button if b.label == "Regenerate quote"]
    check("a Regenerate quote button is rendered when stale", len(regenerate_buttons) == 1)
    regenerate_buttons[0].click().run()
    check("clicking Regenerate renders no exception", not at3.exception)

    v2 = db.get_active_quote(conn, job_id)
    check("clicking Regenerate wrote v2", v2["version"] == 2)


def main() -> None:
    conn = db.connect()
    db.initialize(conn)

    job_id = test_v1_auto_persists_and_rerun_is_idempotent(conn)
    test_inventory_change_triggers_regeneration(conn, job_id)
    test_unconfirmed_flag_costs_no_money(conn, job_id)
    test_correction_becomes_surcharge_eligible(conn, job_id)
    test_staff_review_reasons_cover_escalated_and_unmeasured(conn)
    test_staff_review_reasons_flags_oversize_truck()
    test_boxed_goods_included_without_visiting_review(conn)
    test_declared_volume_and_surcharge_tiers(conn, job_id)
    test_quote_page_via_apptest()

    print(f"\n{PASS_COUNT} checks passed.")


if __name__ == "__main__":
    sys.exit(main())
