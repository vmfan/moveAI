"""Bridges pipeline output and intake fields to the db.py persistence layer.

Pure logic, no Streamlit imports -- mirrors how db.py/pricing.py stay
Streamlit-agnostic (IMPLEMENTATION_ROADMAP.md Build 4). geometry types are
only needed for type hints, so they're imported under TYPE_CHECKING to keep
this module importable without the model stack.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import db

if TYPE_CHECKING:
    import sqlite3

    from geometry import MeasurementFailure, ObjectMeasurement


INTAKE_FIELDS = (
    "contact_name",
    "contact_email",
    "contact_phone",
    "origin_address",
    "origin_floor",
    "origin_has_lift",
    "origin_parking_distance_m",
    "destination_address",
    "destination_floor",
    "destination_has_lift",
    "destination_parking_distance_m",
    "room_count",
    "preferred_move_date",
)


def intake_validation_errors(fields: dict) -> list[str]:
    """Validate an intake form payload before it reaches db.save_intake().

    Returns an empty list when the payload is acceptable.
    """
    errors: list[str] = []

    contact_name = str(fields.get("contact_name") or "").strip()
    if not contact_name:
        errors.append("Contact name is required.")

    contact_email = str(fields.get("contact_email") or "").strip()
    if not contact_email:
        errors.append("Contact email is required.")
    elif "@" not in contact_email or "." not in contact_email.split("@")[-1]:
        errors.append("Contact email doesn't look valid.")

    origin_address = str(fields.get("origin_address") or "").strip()
    if not origin_address:
        errors.append("Origin address is required.")

    destination_address = str(fields.get("destination_address") or "").strip()
    if not destination_address:
        errors.append("Destination address is required.")

    for floor_field in ("origin_floor", "destination_floor"):
        value = fields.get(floor_field)
        if value is not None and float(value) < 0:
            errors.append(f"{floor_field.replace('_', ' ').title()} cannot be negative.")

    for parking_field in ("origin_parking_distance_m", "destination_parking_distance_m"):
        value = fields.get(parking_field)
        if value is not None and float(value) < 0:
            errors.append(
                f"{parking_field.replace('_', ' ').title()} cannot be negative."
            )

    room_count = fields.get("room_count")
    if room_count is not None and int(room_count) < 1:
        errors.append("Room count must be at least 1.")

    return errors


def persist_capture(
    conn: "sqlite3.Connection",
    job_id: int,
    *,
    measurements: list["ObjectMeasurement"],
    failures: list["MeasurementFailure"],
    room_label: str | None,
    source_image_name: str,
    focal_length_px: float,
) -> dict:
    """Persist one capture's measured items and failures as inventory rows.

    Re-running the same photo replaces its prior rows (matched by
    `source_image_name`) rather than duplicating them -- a customer re-taking
    a photo shouldn't double their inventory. Returns a summary dict with the
    new row IDs.
    """
    existing = db.list_inventory_items(conn, job_id)
    for item in existing:
        if item.get("source_image_name") == source_image_name:
            db.delete_inventory_item(conn, item["id"])

    provenance = {
        "capture_mode": "single_image",
        "frames": [
            {
                "image_name": source_image_name,
                "focal_length_px": focal_length_px,
            }
        ],
    }

    measured_ids: list[int] = []
    for measurement in measurements:
        item_id = db.add_inventory_item(
            conn,
            job_id,
            label=measurement.label,
            measurement_basis="measured",
            room_label=room_label,
            width_m=measurement.width_m,
            height_m=measurement.height_m,
            depth_m=measurement.depth_m,
            unit_volume_m3=measurement.visible_obb_volume_m3,
            detection_confidence=measurement.detection_score,
            point_count=measurement.point_count,
            used_axis_aligned_fallback=measurement.used_axis_aligned_fallback,
            mask_touches_border=measurement.mask_touches_border,
            source_image_name=source_image_name,
            provenance_json=provenance,
        )
        measured_ids.append(item_id)

    escalated_ids: list[int] = []
    for failure in failures:
        item_id = db.add_inventory_item(
            conn,
            job_id,
            label=failure.label,
            measurement_basis="measured",
            room_label=room_label,
            detection_confidence=failure.detection_score,
            measurement_error=failure.message,
            review_state="staff_escalate",
            review_reason=f"Measurement failed: {failure.message}",
            source_image_name=source_image_name,
            provenance_json=provenance,
        )
        escalated_ids.append(item_id)

    return {
        "measured_item_ids": measured_ids,
        "escalated_item_ids": escalated_ids,
    }
