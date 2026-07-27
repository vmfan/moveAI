"""Self-check for db.py: exercises the full job -> quote -> booking lifecycle
against a throwaway SQLite file, plus the negative CHECK-constraint cases.

Run with: .venv/bin/python db_smoke_test.py
"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path

import db


PASS_COUNT = 0


def check(description: str, condition: bool) -> None:
    global PASS_COUNT
    if not condition:
        raise AssertionError(f"FAIL: {description}")
    PASS_COUNT += 1
    print(f"PASS: {description}")


def expect_integrity_error(description: str, fn) -> None:
    try:
        fn()
    except sqlite3.IntegrityError:
        check(description, True)
    else:
        raise AssertionError(f"FAIL: {description} (expected sqlite3.IntegrityError)")


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "smoke_test.db"
        conn = db.connect(db_path)

        # 1. initialize() twice: idempotent, single seeded pricing_config row.
        db.initialize(conn)
        db.initialize(conn)
        pricing_rows = conn.execute("SELECT COUNT(*) AS n FROM pricing_config").fetchone()
        check("initialize() is idempotent and seeds exactly one pricing_config row", pricing_rows["n"] == 1)
        active_config = db.get_active_pricing_config(conn)
        check("seeded pricing_config is active", active_config is not None and active_config["is_active"] == 1)
        check("seeded pricing_config currency is HKD", active_config["currency"] == "HKD")

        # 2. Job -> intake, including a re-submit (upsert, not duplicate).
        job_id = db.create_job(conn)
        check("create_job returns an id", isinstance(job_id, int) and job_id > 0)

        db.save_intake(
            conn,
            job_id,
            contact_name="Alice Chan",
            contact_email="alice@example.com",
            contact_phone="+852 1234 5678",
            origin_address="1 Queen's Road, HK",
            origin_floor=3,
            origin_has_lift=0,
            origin_parking_distance_m=20,
            destination_address="88 Nathan Road, HK",
            destination_floor=0,
            destination_has_lift=0,
            destination_parking_distance_m=5,
            room_count=2,
            preferred_move_date="2026-08-15",
        )
        db.save_intake(
            conn,
            job_id,
            contact_name="Alice Chan-Wong",
            contact_email="alice@example.com",
            contact_phone="+852 1234 5678",
            origin_address="1 Queen's Road, HK",
            origin_floor=3,
            origin_has_lift=0,
            origin_parking_distance_m=20,
            destination_address="88 Nathan Road, HK",
            destination_floor=0,
            destination_has_lift=0,
            destination_parking_distance_m=5,
            room_count=3,
            preferred_move_date="2026-08-15",
        )
        intake_rows = conn.execute(
            "SELECT COUNT(*) AS n FROM intake WHERE job_id = ?", (job_id,)
        ).fetchone()
        check("save_intake upserts rather than duplicating", intake_rows["n"] == 1)
        intake = db.get_intake(conn, job_id)
        check("re-submitted intake reflects the update", intake["contact_name"] == "Alice Chan-Wong" and intake["room_count"] == 3)

        # 3. Four inventory rows covering every line type.
        measured_id = db.add_inventory_item(
            conn,
            job_id,
            label="Sofa",
            measurement_basis="measured",
            width_m=2.1,
            height_m=0.85,
            depth_m=0.9,
            unit_volume_m3=1.6,
            detection_confidence=0.92,
            point_count=4200,
            review_state="auto_accept",
        )
        prior_assisted_id = db.add_inventory_item(
            conn,
            job_id,
            label="Wardrobe",
            measurement_basis="prior_assisted",
            width_m=1.2,
            height_m=2.0,
            depth_m=0.6,
            unit_volume_m3=1.44,
            prior_assisted_axes=["depth_m"],
            detection_confidence=0.81,
            point_count=3100,
            review_state="auto_accept",
        )
        boxed_goods_id = db.add_boxed_goods_item(
            conn,
            job_id,
            label="Boxed goods (kitchen)",
            quantity=12,
            unit_volume_m3=0.11,
            boxed_goods_seed_json={"seeded_from": "cabinet", "room_count": 2},
        )
        escalated_id = db.add_inventory_item(
            conn,
            job_id,
            label="Unidentified bulky item",
            measurement_basis="measured",
            measurement_error="Not enough valid depth pixels inside the object mask.",
            review_state="staff_escalate",
            review_reason="measurement_failed",
        )
        items = db.list_inventory_items(conn, job_id)
        check("all four inventory line types were inserted", len(items) == 4)
        prior_item = db.get_inventory_item(conn, prior_assisted_id)
        check("prior_assisted_axes round-trips as a list", prior_item["prior_assisted_axes"] == ["depth_m"])
        boxed_item = db.get_inventory_item(conn, boxed_goods_id)
        check("boxed goods line has no dimensions", boxed_item["width_m"] is None and boxed_item["depth_m"] is None)
        check("boxed goods line carries its seed", boxed_item["boxed_goods_seed_json"]["seeded_from"] == "cabinet")

        # 4. Confirming an escalated item must not clear the escalation.
        db.set_customer_confirmed(conn, escalated_id, True)
        escalated_item = db.get_inventory_item(conn, escalated_id)
        check(
            "customer_confirmed does not clear staff_escalate",
            escalated_item["customer_confirmed"] == 1 and escalated_item["review_state"] == "staff_escalate",
        )

        # 5. Quote v1 -> amend inventory -> quote v2; versioning + supersession.
        quote_v1_id = db.create_quote(
            conn,
            job_id,
            pricing_config_id=active_config["id"],
            total_volume_m3=3.04,
            upper_bound_volume_m3=3.5,
            volume_margin_fraction=0.15,
            access_multiplier=1.08,
            total_price=2200.0,
            recommended_truck="7.5t",
            lines=[
                {
                    "inventory_item_id": measured_id,
                    "measurement_basis": "measured",
                    "volume_m3": 1.6,
                    "price_component": 900.0,
                },
                {
                    "inventory_item_id": boxed_goods_id,
                    "measurement_basis": "declared",
                    "volume_m3": 1.32,
                    "price_component": 500.0,
                },
            ],
        )
        db.update_inventory_item(conn, boxed_goods_id, quantity=20)
        quote_v2_id = db.create_quote(
            conn,
            job_id,
            pricing_config_id=active_config["id"],
            total_volume_m3=4.24,
            upper_bound_volume_m3=4.9,
            volume_margin_fraction=0.15,
            access_multiplier=1.08,
            total_price=2800.0,
            recommended_truck="10t",
            lines=[
                {
                    "inventory_item_id": measured_id,
                    "measurement_basis": "measured",
                    "volume_m3": 1.6,
                    "price_component": 900.0,
                },
                {
                    "inventory_item_id": boxed_goods_id,
                    "measurement_basis": "declared",
                    "volume_m3": 2.2,
                    "price_component": 900.0,
                },
            ],
        )
        quotes = db.list_quotes(conn, job_id)
        check("both quote versions persisted", len(quotes) == 2)
        v1 = next(q for q in quotes if q["id"] == quote_v1_id)
        v2 = next(q for q in quotes if q["id"] == quote_v2_id)
        check("v1 is superseded", v1["is_superseded"] == 1)
        check("v2 is not superseded", v2["is_superseded"] == 0)
        active_quote = db.get_active_quote(conn, job_id)
        check("get_active_quote returns v2", active_quote["id"] == quote_v2_id)

        v2_lines = db.get_quote_lines(conn, quote_v2_id)
        measured_line = next(l for l in v2_lines if l["inventory_item_id"] == measured_id)
        declared_line = next(l for l in v2_lines if l["inventory_item_id"] == boxed_goods_id)
        check("measurement_basis survives onto the quote line", measured_line["measurement_basis"] == "measured")
        check("surcharge_eligible tracks measurement_basis (measured -> not eligible)", measured_line["surcharge_eligible"] == 0)
        check("surcharge_eligible tracks measurement_basis (declared -> eligible)", declared_line["surcharge_eligible"] == 1)

        # 6. Booking lifecycle.
        booking_id = db.create_booking(conn, job_id, quote_v2_id, customer_note="Please call ahead")
        booking = db.list_bookings(conn)[0]
        check("booking starts pending_staff_review", booking["status"] == "pending_staff_review")
        db.update_booking_status(conn, booking_id, "confirmed", staff_note="Confirmed by ops")
        confirmed = db.list_bookings(conn, status="confirmed")
        check("booking status transition persists", len(confirmed) == 1 and confirmed[0]["id"] == booking_id)

        # 7. Negative cases -- each must raise sqlite3.IntegrityError.
        expect_integrity_error(
            "boxed goods item with dimensions violates CHECK",
            lambda: conn.execute(
                """
                INSERT INTO inventory_item (
                    job_id, label, measurement_basis, is_boxed_goods, quantity,
                    width_m, review_state, created_at, updated_at
                ) VALUES (?, 'Bad boxed goods', 'declared', 1, 5, 1.0, 'auto_accept', 'x', 'x')
                """,
                (job_id,),
            ),
        )
        expect_integrity_error(
            "invalid measurement_basis violates CHECK",
            lambda: conn.execute(
                """
                INSERT INTO inventory_item (
                    job_id, label, measurement_basis, quantity, review_state, created_at, updated_at
                ) VALUES (?, 'Bad basis', 'guessed', 1, 'auto_accept', 'x', 'x')
                """,
                (job_id,),
            ),
        )
        expect_integrity_error(
            "surcharge_eligible disagreeing with measurement_basis violates CHECK",
            lambda: conn.execute(
                """
                INSERT INTO quote_line (
                    quote_id, inventory_item_id, measurement_basis, volume_m3,
                    price_component, surcharge_eligible
                ) VALUES (?, ?, 'measured', 1.0, 100.0, 1)
                """,
                (quote_v2_id, measured_id),
            ),
        )
        expect_integrity_error(
            "a second active pricing_config violates the partial unique index",
            lambda: conn.execute(
                """
                INSERT INTO pricing_config (
                    name, currency, base_callout_fee, price_per_m3, minimum_charge,
                    volume_margin_fraction, floor_multiplier_per_level, lift_multiplier,
                    parking_multiplier_per_10m, max_access_multiplier,
                    boxed_goods_labour_multiplier, volume_per_box_m3,
                    is_active, created_at
                ) VALUES ('Rogue config', 'HKD', 1, 1, 1, 0.1, 0.1, 1.0, 0.1, 2.0, 1.0, 0.1, 1, 'x')
                """
            ),
        )

        conn.close()

    print(f"\n{PASS_COUNT} checks passed.")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)
