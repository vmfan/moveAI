"""Self-check for Build 4: the intake form, the job spine, and persisting a
capture's measurements/failures into inventory_item rows.

Verifies validation, persist_capture()'s round-trip through db.py (including
re-capture idempotency and the mandatory-escalation rule for failures), the
border-touching signal in geometry.py, and that a saved intake satisfies
pricing.py's AccessFactors contract from Build 3. Also drives the real
Streamlit Intake page headlessly via AppTest, since the environment can't run
the live pipeline (IMPLEMENTATION_ROADMAP.md's "Known environment
constraints").

Run with: .venv/bin/python job_flow_smoke_test.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# Must be set before `config`/`db` are imported anywhere in this process,
# including transitively via AppTest running pages/1_Intake.py and app.py.
_TMP_DIR = tempfile.mkdtemp()
os.environ["MOVEAI_DB_PATH"] = str(Path(_TMP_DIR) / "app_test.db")

import numpy as np

import db
import pricing
from geometry import MeasurementFailure, ObjectMeasurement, _mask_touches_border
from inventory_sync import intake_validation_errors, persist_capture


PASS_COUNT = 0


def check(description: str, condition: bool) -> None:
    global PASS_COUNT
    if not condition:
        raise AssertionError(f"FAIL: {description}")
    PASS_COUNT += 1
    print(f"PASS: {description}")


VALID_INTAKE = {
    "contact_name": "Amy Chan",
    "contact_email": "amy@example.com",
    "contact_phone": "+852 1234 5678",
    "origin_address": "1 Nathan Road, TST",
    "origin_floor": 3,
    "origin_has_lift": False,
    "origin_parking_distance_m": 5.0,
    "destination_address": "88 Queensway, Admiralty",
    "destination_floor": 0,
    "destination_has_lift": True,
    "destination_parking_distance_m": 0.0,
    "room_count": 3,
    "preferred_move_date": "2026-08-15",
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


def test_validation() -> None:
    check(
        "valid payload passes validation",
        intake_validation_errors(VALID_INTAKE) == [],
    )

    missing_name = dict(VALID_INTAKE, contact_name="  ")
    check(
        "missing contact name is rejected",
        "Contact name is required." in intake_validation_errors(missing_name),
    )

    missing_email = dict(VALID_INTAKE, contact_email="")
    check(
        "missing email is rejected",
        "Contact email is required." in intake_validation_errors(missing_email),
    )

    bad_email = dict(VALID_INTAKE, contact_email="not-an-email")
    check(
        "malformed email is rejected",
        any("valid" in e for e in intake_validation_errors(bad_email)),
    )

    missing_origin = dict(VALID_INTAKE, origin_address="")
    check(
        "missing origin address is rejected",
        "Origin address is required." in intake_validation_errors(missing_origin),
    )

    missing_destination = dict(VALID_INTAKE, destination_address="   ")
    check(
        "missing destination address is rejected",
        "Destination address is required."
        in intake_validation_errors(missing_destination),
    )

    negative_floor = dict(VALID_INTAKE, origin_floor=-1)
    check(
        "negative floor is rejected",
        len(intake_validation_errors(negative_floor)) > 0,
    )

    zero_rooms = dict(VALID_INTAKE, room_count=0)
    check(
        "room_count < 1 is rejected",
        "Room count must be at least 1." in intake_validation_errors(zero_rooms),
    )


def test_intake_feeds_pricing_contract(conn) -> None:
    job_id = db.create_job(conn)
    db.save_intake(conn, job_id, **VALID_INTAKE)
    intake = db.get_intake(conn, job_id)

    access = pricing.AccessFactors.from_intake(intake)
    check(
        "AccessFactors.from_intake() consumes a saved intake with no KeyError",
        access.origin_floor == 3 and access.destination_has_lift is True,
    )

    config = db.get_active_pricing_config(conn)
    multiplier = pricing.access_multiplier(access, config)
    check(
        "a 3rd-floor no-lift origin raises the access multiplier above 1.0",
        multiplier > 1.0,
    )


def test_border_signal() -> None:
    interior = np.zeros((100, 100), dtype=bool)
    interior[40:60, 40:60] = True
    check("interior mask does not touch border", _mask_touches_border(interior) is False)

    edge = np.zeros((100, 100), dtype=bool)
    edge[0, 50] = True
    check("top-row mask touches border", _mask_touches_border(edge) is True)

    edge_col = np.zeros((100, 100), dtype=bool)
    edge_col[50, -1] = True
    check("last-column mask touches border", _mask_touches_border(edge_col) is True)


def test_persist_capture(conn) -> None:
    job_id = db.create_job(conn)
    db.save_intake(conn, job_id, **VALID_INTAKE)

    sofa = _measurement("sofa", width_m=2.1, height_m=0.9, depth_m=0.85)
    lamp = _measurement("floor lamp", mask_touches_border=True)
    failure = MeasurementFailure(
        index=3, label="bookshelf", detection_score=0.4, message="Not enough valid depth pixels."
    )

    summary = persist_capture(
        conn,
        job_id,
        measurements=[sofa, lamp],
        failures=[failure],
        room_label="Living room",
        source_image_name="living_room_1.jpg",
        focal_length_px=1450.0,
    )
    check(
        "persist_capture returns 2 measured + 1 escalated id",
        len(summary["measured_item_ids"]) == 2
        and len(summary["escalated_item_ids"]) == 1,
    )

    items = db.list_inventory_items(conn, job_id)
    check("3 inventory rows were written", len(items) == 3)

    sofa_row = next(i for i in items if i["label"] == "sofa")
    check(
        "named dimensions round-trip",
        (sofa_row["width_m"], sofa_row["height_m"], sofa_row["depth_m"])
        == (2.1, 0.9, 0.85),
    )
    check("room_label was applied", sofa_row["room_label"] == "Living room")
    check(
        "provenance carries frame info",
        sofa_row["provenance_json"]["frames"][0]["image_name"] == "living_room_1.jpg",
    )

    lamp_row = next(i for i in items if i["label"] == "floor lamp")
    check("border-touching signal persists", lamp_row["mask_touches_border"] == 1)

    escalated_row = next(i for i in items if i["label"] == "bookshelf")
    check(
        "failed measurement becomes a staff_escalate row, not a dropped log line",
        escalated_row["review_state"] == "staff_escalate",
    )
    check(
        "escalated row carries the failure message",
        escalated_row["measurement_error"] == "Not enough valid depth pixels.",
    )
    check(
        "escalated row has no dimensions",
        escalated_row["width_m"] is None and escalated_row["depth_m"] is None,
    )

    # Re-capture the same photo: rows are replaced, not duplicated.
    sofa_v2 = _measurement("sofa", width_m=2.15, height_m=0.9, depth_m=0.85)
    persist_capture(
        conn,
        job_id,
        measurements=[sofa_v2],
        failures=[],
        room_label="Living room",
        source_image_name="living_room_1.jpg",
        focal_length_px=1450.0,
    )
    items_after_recapture = db.list_inventory_items(conn, job_id)
    check(
        "re-capturing the same image replaces its rows, not duplicates them",
        len(items_after_recapture) == 1
        and items_after_recapture[0]["width_m"] == 2.15,
    )

    # A different photo adds alongside rather than replacing.
    persist_capture(
        conn,
        job_id,
        measurements=[_measurement("dining table")],
        failures=[],
        room_label="Dining room",
        source_image_name="dining_room_1.jpg",
        focal_length_px=1400.0,
    )
    items_after_second_photo = db.list_inventory_items(conn, job_id)
    check(
        "a second, distinct photo adds alongside the first",
        len(items_after_second_photo) == 2,
    )


def test_ties_through_to_quote(conn) -> None:
    job_id = db.create_job(conn)
    db.save_intake(conn, job_id, **VALID_INTAKE)
    persist_capture(
        conn,
        job_id,
        measurements=[_measurement("sofa", width_m=2.1, height_m=0.9, depth_m=0.85)],
        failures=[
            MeasurementFailure(
                index=1, label="cabinet", detection_score=0.5, message="failed"
            )
        ],
        room_label="Living room",
        source_image_name="tie_through.jpg",
        focal_length_px=1450.0,
    )

    intake = db.get_intake(conn, job_id)
    config = db.get_active_pricing_config(conn)
    items = db.list_inventory_items(conn, job_id)
    quote = pricing.build_quote(items, intake, config)

    check("the measured sofa produces a priced line", len(quote.lines) == 1)
    check(
        "the escalated cabinet is reported, not silently dropped",
        len(quote.escalated_item_ids) == 1,
    )


def test_intake_page_via_apptest() -> None:
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file("pages/1_Intake.py")
    at.run()
    check("Intake page renders with no exception", not at.exception)

    at.text_input[0].set_value("Bo Wong")  # Full name
    at.text_input[1].set_value("bo@example.com")  # Email
    at.number_input[0].set_value(2)  # Origin floor
    at.checkbox[0].set_value(False)  # Origin lift
    at.number_input[1].set_value(0.0)  # Origin parking distance
    at.number_input[2].set_value(0)  # Destination floor
    at.checkbox[1].set_value(True)  # Destination lift
    at.number_input[3].set_value(0.0)  # Destination parking distance
    at.number_input[4].set_value(2)  # Room count

    # Addresses are text_area widgets.
    at.text_area[0].set_value("10 Test Street")
    at.text_area[1].set_value("20 Sample Avenue")

    submit = next(b for b in at.button if "Save intake" in b.label)
    submit.click().run()
    check("submitting the form renders no exception", not at.exception)
    check(
        "submitting the form set an active job_id",
        "job_id" in at.session_state and at.session_state["job_id"] is not None,
    )

    job_id = at.session_state["job_id"]
    conn = db.connect()
    intake = db.get_intake(conn, job_id)
    check(
        "the intake row was actually written via the real page",
        intake is not None and intake["contact_name"] == "Bo Wong",
    )
    check(
        "job_id round-tripped into st.query_params",
        dict(at.query_params).get("job_id") == [str(job_id)],
    )

    # Re-run the page: fields should prefill from the now-active job.
    at2 = AppTest.from_file("pages/1_Intake.py")
    at2.session_state["job_id"] = job_id
    at2.run()
    check("re-running the page with an active job renders no exception", not at2.exception)
    check(
        "the name field prefills from the saved intake",
        at2.text_input[0].value == "Bo Wong",
    )


def test_app_standalone_mode() -> None:
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file("app.py")
    at.run()
    check("app.py renders with no exception with no active job", not at.exception)


def main() -> None:
    conn = db.connect()
    db.initialize(conn)

    test_validation()
    test_border_signal()
    test_intake_feeds_pricing_contract(conn)
    test_persist_capture(conn)
    test_ties_through_to_quote(conn)
    test_intake_page_via_apptest()
    test_app_standalone_mode()

    print(f"\n{PASS_COUNT} checks passed.")


if __name__ == "__main__":
    sys.exit(main())
