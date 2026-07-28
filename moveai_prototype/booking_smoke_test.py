"""Self-check for Build 7: the booking request queue and Company Console.

Verifies `booking_sync.booking_blockers()` only fires on the two hard
conditions (no quote yet, or the active quote is stale against current
inventory -- IMPLEMENTATION_ROADMAP.md Build 7's "send them back to Quote"
decision), that an unconfirmed/escalated item never blocks a submission
(DESIGN.md SS5c extended to booking: a flagged job may request a booking, it
just can't be auto-approved), `submit_booking()`'s rerun-idempotency,
`job.status` only becoming 'booked' on staff confirmation (never on
customer submit), the clarification round trip, and drives the real
Booking and Company Console pages headlessly via AppTest, since the
environment can't run the live pipeline (IMPLEMENTATION_ROADMAP.md's
"Known environment constraints").

Run with: .venv/bin/python booking_smoke_test.py
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
from inventory_sync import add_declared_item, persist_capture, seed_boxed_goods
from quote_sync import persist_quote
from booking_sync import (
    active_booking,
    apply_staff_decision,
    booking_blockers,
    console_rows,
    resubmit_booking,
    submit_booking,
)


PASS_COUNT = 0


def check(description: str, condition: bool) -> None:
    global PASS_COUNT
    if not condition:
        raise AssertionError(f"FAIL: {description}")
    PASS_COUNT += 1
    print(f"PASS: {description}")


VALID_INTAKE = {
    "contact_name": "Amy Lam",
    "contact_email": "amy@example.com",
    "contact_phone": "+852 9123 4567",
    "origin_address": "10 Nathan Road, TST",
    "origin_floor": 3,
    "origin_has_lift": False,
    "origin_parking_distance_m": 5.0,
    "destination_address": "88 Queensway, Admiralty",
    "destination_floor": 1,
    "destination_has_lift": True,
    "destination_parking_distance_m": 0.0,
    "room_count": 2,
    "preferred_move_date": "2026-10-01",
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
        measurements=[_measurement("sofa")],
        failures=[],
        room_label="Living room",
        source_image_name="booking_test.jpg",
        focal_length_px=1400.0,
    )
    config = db.get_active_pricing_config(conn)
    seed_boxed_goods(
        conn, job_id, room_count=2, volume_per_box_m3=float(config["volume_per_box_m3"])
    )
    return job_id


def test_blockers_before_any_quote(conn) -> int:
    job_id = _setup_job(conn)
    intake = db.get_intake(conn, job_id)
    config = db.get_active_pricing_config(conn)
    items = db.list_inventory_items(conn, job_id)
    fresh_quote = pricing.build_quote(items, intake, config)

    blockers = booking_blockers(None, [], fresh_quote)
    check("no quote yet blocks submission", len(blockers) == 1)

    return job_id


def test_stale_quote_blocks(conn, job_id) -> None:
    intake = db.get_intake(conn, job_id)
    config = db.get_active_pricing_config(conn)
    items = db.list_inventory_items(conn, job_id)
    quote = pricing.build_quote(items, intake, config)
    persist_quote(conn, job_id, quote, pricing_config_id=config["id"])
    v1 = db.get_active_quote(conn, job_id)
    v1_lines = db.get_quote_lines(conn, v1["id"])

    blockers = booking_blockers(v1, v1_lines, quote)
    check("blockers are empty when the quote matches", blockers == [])

    add_declared_item(
        conn,
        job_id,
        label="Bookshelf",
        room_label="Living room",
        quantity=1,
        width_m=1.0,
        height_m=1.8,
        depth_m=0.4,
    )
    items = db.list_inventory_items(conn, job_id)
    fresh_quote = pricing.build_quote(items, intake, config)
    blockers = booking_blockers(v1, v1_lines, fresh_quote)
    check(
        "a stale quote (inventory changed) blocks submission and names the staleness",
        len(blockers) == 1 and "changed" in blockers[0],
    )

    persist_quote(conn, job_id, fresh_quote, pricing_config_id=config["id"])
    v2 = db.get_active_quote(conn, job_id)
    v2_lines = db.get_quote_lines(conn, v2["id"])
    blockers = booking_blockers(v2, v2_lines, fresh_quote)
    check("regenerating clears the blocker", blockers == [])


def test_submit_creates_booking_and_leaves_job_quoted(conn, job_id) -> int:
    quote_row = db.get_active_quote(conn, job_id)
    check("job status is quoted before submit", db.get_job(conn, job_id)["status"] == "quoted")

    booking_id, created = submit_booking(conn, job_id, quote_row["id"], customer_note="Please call ahead.")
    check("submit creates a booking", created is True)

    booking = db.get_booking(conn, booking_id)
    check("booking status starts pending_staff_review", booking["status"] == "pending_staff_review")
    check("booking pins the active quote id", booking["quote_id"] == quote_row["id"])
    check(
        "job status stays quoted, not booked, on customer submit",
        db.get_job(conn, job_id)["status"] == "quoted",
    )

    return booking_id


def test_submit_is_idempotent(conn, job_id, booking_id) -> None:
    quote_row = db.get_active_quote(conn, job_id)
    second_id, created = submit_booking(conn, job_id, quote_row["id"], customer_note="Different note")
    check("a second submit returns the same booking id", second_id == booking_id)
    check("a second submit does not create a new row", created is False)

    rows = db.list_bookings(conn, job_id=job_id)
    check("still only one booking row exists", len(rows) == 1)


def test_staff_confirm_books_the_job(conn, job_id, booking_id) -> None:
    apply_staff_decision(conn, booking_id, "confirmed", staff_note="Confirmed for Oct 1.")
    booking = db.get_booking(conn, booking_id)
    check("booking status is confirmed", booking["status"] == "confirmed")
    check("staff note stored", booking["staff_note"] == "Confirmed for Oct 1.")
    check("job status becomes booked only on staff confirm", db.get_job(conn, job_id)["status"] == "booked")


def test_clarification_round_trip(conn) -> None:
    conn2 = conn
    job_id = db.create_job(conn2)
    db.save_intake(conn2, job_id, **VALID_INTAKE)
    persist_capture(
        conn2,
        job_id,
        measurements=[_measurement("wardrobe")],
        failures=[],
        room_label="Bedroom",
        source_image_name="clarify_test.jpg",
        focal_length_px=1400.0,
    )
    config = db.get_active_pricing_config(conn2)
    seed_boxed_goods(conn2, job_id, room_count=2, volume_per_box_m3=float(config["volume_per_box_m3"]))
    intake = db.get_intake(conn2, job_id)
    items = db.list_inventory_items(conn2, job_id)
    quote = pricing.build_quote(items, intake, config)
    persist_quote(conn2, job_id, quote, pricing_config_id=config["id"])
    quote_row = db.get_active_quote(conn2, job_id)

    booking_id, _ = submit_booking(conn2, job_id, quote_row["id"])
    apply_staff_decision(conn2, booking_id, "needs_customer_clarification", staff_note="Is the wardrobe empty?")
    booking = db.get_booking(conn2, booking_id)
    check("clarification sets the status", booking["status"] == "needs_customer_clarification")
    check(
        "job status is untouched by a clarification request",
        db.get_job(conn2, job_id)["status"] == "quoted",
    )

    resubmit_booking(conn2, booking_id, customer_note="Yes, it will be empty.")
    booking = db.get_booking(conn2, booking_id)
    check("resubmit flips back to pending_staff_review", booking["status"] == "pending_staff_review")
    check("resubmit attaches the customer reply", booking["customer_note"] == "Yes, it will be empty.")
    check("resubmit preserves the staff note", booking["staff_note"] == "Is the wardrobe empty?")

    raised = False
    try:
        resubmit_booking(conn2, booking_id, customer_note="too soon")
    except ValueError:
        raised = True
    check("resubmitting from the wrong state raises ValueError", raised)


def test_staff_cancel_and_resubmission(conn, job_id) -> None:
    booking = active_booking(conn, job_id)
    check("precondition: booking is confirmed", booking["status"] == "confirmed")

    apply_staff_decision(conn, booking["id"], "cancelled", staff_note="Customer cancelled.")
    check("job status becomes cancelled on staff cancel", db.get_job(conn, job_id)["status"] == "cancelled")

    db.set_job_status(conn, job_id, "quoted")
    quote_row = db.get_active_quote(conn, job_id)
    new_id, created = submit_booking(conn, job_id, quote_row["id"])
    check("a new submission after cancellation creates a second row", created is True and new_id != booking["id"])

    rows = db.list_bookings(conn, job_id=job_id)
    check("two distinct booking rows now exist for this job", len(rows) == 2)


def test_console_rows_and_non_blocking_reasons(conn) -> None:
    conn2 = conn
    job_id = db.create_job(conn2)
    db.save_intake(conn2, job_id, **VALID_INTAKE)
    persist_capture(
        conn2,
        job_id,
        measurements=[_measurement("armchair", mask_touches_border=True)],
        failures=[],
        room_label="Living room",
        source_image_name="console_test.jpg",
        focal_length_px=1400.0,
    )
    config = db.get_active_pricing_config(conn2)
    seed_boxed_goods(conn2, job_id, room_count=2, volume_per_box_m3=float(config["volume_per_box_m3"]))
    intake = db.get_intake(conn2, job_id)
    items = db.list_inventory_items(conn2, job_id)

    armchair = next(i for i in items if i["label"] == "armchair")
    check(
        "precondition: armchair is an unconfirmed customer_confirm item",
        armchair["review_state"] == "customer_confirm",
    )

    quote = pricing.build_quote(items, intake, config)
    persist_quote(conn2, job_id, quote, pricing_config_id=config["id"])
    quote_row = db.get_active_quote(conn2, job_id)

    blockers = booking_blockers(quote_row, db.get_quote_lines(conn2, quote_row["id"]), quote)
    check(
        "an unconfirmed flagged item does not block submission (§5c: review, not money)",
        blockers == [],
    )

    booking_id, _ = submit_booking(conn2, job_id, quote_row["id"])

    rows = console_rows(conn2, status="pending_staff_review")
    row = next(r for r in rows if r["booking"]["id"] == booking_id)
    check("console row carries the contact name", row["intake"]["contact_name"] == "Amy Lam")
    check(
        "console row surfaces the unconfirmed armchair as a (non-blocking) reason",
        any("armchair" in r for r in row["reasons"]),
    )
    check("pinned quote is not superseded yet", row["pinned_quote_superseded"] is False)

    # Regenerate the quote (simulating a later customer edit) and confirm the
    # console flags the booking's pinned quote as superseded.
    add_declared_item(
        conn2, job_id, label="Extra box", room_label="Living room", quantity=1,
        width_m=0.4, height_m=0.4, depth_m=0.4,
    )
    items2 = db.list_inventory_items(conn2, job_id)
    fresh_quote = pricing.build_quote(items2, intake, config)
    persist_quote(conn2, job_id, fresh_quote, pricing_config_id=config["id"])

    rows = console_rows(conn2, status="pending_staff_review")
    row = next(r for r in rows if r["booking"]["id"] == booking_id)
    check("console flags a superseded pinned quote", row["pinned_quote_superseded"] is True)


def test_booking_page_via_apptest() -> None:
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file("pages/4_Booking.py")
    at.run()
    check("Booking page renders with no active job", not at.exception)

    conn = db.connect()
    job_id = db.create_job(conn)
    db.save_intake(conn, job_id, **VALID_INTAKE)
    persist_capture(
        conn,
        job_id,
        measurements=[_measurement("dining table")],
        failures=[],
        room_label="Living room",
        source_image_name="apptest_booking.jpg",
        focal_length_px=1400.0,
    )

    at2 = AppTest.from_file("pages/4_Booking.py")
    at2.session_state["job_id"] = job_id
    at2.run()
    check("Booking page renders with a seeded job but no quote", not at2.exception)
    request_buttons = [b for b in at2.button if b.label == "Request booking"]
    check("no Request booking button without a quote yet (blocked)", len(request_buttons) == 0)

    intake = db.get_intake(conn, job_id)
    config = db.get_active_pricing_config(conn)
    items = db.list_inventory_items(conn, job_id)
    quote = pricing.build_quote(items, intake, config)
    persist_quote(conn, job_id, quote, pricing_config_id=config["id"])

    at3 = AppTest.from_file("pages/4_Booking.py")
    at3.session_state["job_id"] = job_id
    at3.run()
    check("Booking page renders once a quote exists", not at3.exception)
    request_buttons = [b for b in at3.button if b.label == "Request booking"]
    check("a Request booking button is rendered once unblocked", len(request_buttons) == 1)
    request_buttons[0].click().run()
    check("clicking Request booking renders no exception", not at3.exception)
    check("clicking Request booking wrote a booking row", active_booking(conn, job_id) is not None)

    at4 = AppTest.from_file("pages/4_Booking.py")
    at4.session_state["job_id"] = job_id
    at4.run()
    check("revisiting after a request shows no second Request booking button", not at4.exception)
    request_buttons_again = [b for b in at4.button if b.label == "Request booking"]
    check("no duplicate submission is possible from the page", len(request_buttons_again) == 0)
    rows = db.list_bookings(conn, job_id=job_id)
    check("still exactly one booking row", len(rows) == 1)

    # Change the inventory without regenerating the quote and confirm the
    # page blocks a new submission rather than pinning the stale quote.
    add_declared_item(
        conn, job_id, label="Extra lamp", room_label="Living room", quantity=1,
        width_m=0.3, height_m=1.5, depth_m=0.3,
    )
    apply_staff_decision(conn, active_booking(conn, job_id)["id"], "cancelled")
    at5 = AppTest.from_file("pages/4_Booking.py")
    at5.session_state["job_id"] = job_id
    at5.run()
    check("Booking page renders with a stale quote", not at5.exception)
    request_buttons_stale = [b for b in at5.button if b.label == "Request booking"]
    check("no Request booking button when the quote is stale", len(request_buttons_stale) == 0)


def test_company_console_via_apptest() -> None:
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file("pages/5_Company_Console.py")
    at.run()
    check("Company Console renders without error", not at.exception)

    conn = db.connect()
    job_id = db.create_job(conn)
    db.save_intake(conn, job_id, **VALID_INTAKE)
    persist_capture(
        conn,
        job_id,
        measurements=[_measurement("desk")],
        failures=[],
        room_label="Study",
        source_image_name="apptest_console.jpg",
        focal_length_px=1400.0,
    )
    config = db.get_active_pricing_config(conn)
    seed_boxed_goods(conn, job_id, room_count=2, volume_per_box_m3=float(config["volume_per_box_m3"]))
    intake = db.get_intake(conn, job_id)
    items = db.list_inventory_items(conn, job_id)
    quote = pricing.build_quote(items, intake, config)
    persist_quote(conn, job_id, quote, pricing_config_id=config["id"])
    quote_row = db.get_active_quote(conn, job_id)
    booking_id, _ = submit_booking(conn, job_id, quote_row["id"])

    at2 = AppTest.from_file("pages/5_Company_Console.py")
    at2.run()
    check("Company Console renders with a pending booking listed", not at2.exception)
    # Other tests in this suite share the same DB and may leave their own
    # pending bookings behind, so match this booking's Confirm button by its
    # widget key rather than assuming it's the only one in the queue.
    confirm_buttons = [
        b for b in at2.button if b.key == f"confirm_{booking_id}"
    ]
    check("a Confirm button is rendered for the pending booking", len(confirm_buttons) == 1)
    confirm_buttons[0].click().run()
    check("clicking Confirm renders no exception", not at2.exception)

    booking = db.get_booking(conn, booking_id)
    check("clicking Confirm transitions the booking to confirmed", booking["status"] == "confirmed")
    check("clicking Confirm transitions the job to booked", db.get_job(conn, job_id)["status"] == "booked")


def main() -> None:
    conn = db.connect()
    db.initialize(conn)

    job_id = test_blockers_before_any_quote(conn)
    test_stale_quote_blocks(conn, job_id)
    booking_id = test_submit_creates_booking_and_leaves_job_quoted(conn, job_id)
    test_submit_is_idempotent(conn, job_id, booking_id)
    test_staff_confirm_books_the_job(conn, job_id, booking_id)
    test_clarification_round_trip(conn)
    test_staff_cancel_and_resubmission(conn, job_id)
    test_console_rows_and_non_blocking_reasons(conn)
    test_booking_page_via_apptest()
    test_company_console_via_apptest()

    print(f"\n{PASS_COUNT} checks passed.")


if __name__ == "__main__":
    sys.exit(main())
