"""Bridges pipeline output and intake fields to the db.py persistence layer.

Pure logic, no Streamlit imports -- mirrors how db.py/pricing.py stay
Streamlit-agnostic (IMPLEMENTATION_ROADMAP.md Build 4). geometry types are
only needed for type hints, so they're imported under TYPE_CHECKING to keep
this module importable without the model stack.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import boxed_goods
import db
import review_policy

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
        decision = review_policy.classify(
            label=measurement.label,
            detection_confidence=measurement.detection_score,
            point_count=measurement.point_count,
            used_axis_aligned_fallback=measurement.used_axis_aligned_fallback,
            mask_touches_border=measurement.mask_touches_border,
            width_m=measurement.width_m,
            height_m=measurement.height_m,
            depth_m=measurement.depth_m,
        )
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
            shell_ratio=decision.shell_ratio,
            implausible_dimension=decision.implausible_dimension,
            review_state=decision.state,
            review_reason=decision.reason,
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


# --------------------------------------------------------------------------
# Inventory Review (Build 5)
# --------------------------------------------------------------------------


def seed_boxed_goods(
    conn: "sqlite3.Connection",
    job_id: int,
    *,
    room_count: int,
    volume_per_box_m3: float,
) -> dict | None:
    """Seed the job's boxed-goods line if one doesn't already exist.

    Idempotent: re-calling with an existing boxed-goods row returns it
    unchanged rather than seeding a second line (there is exactly one
    boxed-goods line per job -- the customer adjusts the count in place via
    `set_boxed_goods_count()`, they don't get a second seed).

    Seeded `customer_confirm`, not `auto_accept` -- DESIGN.md SS5c's
    surcharge contract only stands up if the customer actually saw and
    owned this number before it became part of the quote.
    """
    existing_items = db.list_inventory_items(conn, job_id)
    existing_boxed = next((i for i in existing_items if i["is_boxed_goods"]), None)
    if existing_boxed is not None:
        return {"item_id": existing_boxed["id"], "created": False, "estimate": None}

    storage_labels = [
        item["label"] for item in existing_items if not item["is_boxed_goods"]
    ]
    estimate = boxed_goods.estimate_boxed_goods(
        storage_labels=storage_labels,
        room_count=room_count,
        volume_per_box_m3=volume_per_box_m3,
    )
    item_id = db.add_boxed_goods_item(
        conn,
        job_id,
        label="Boxed goods (estimated)",
        quantity=estimate.box_count,
        unit_volume_m3=estimate.volume_per_box_m3,
        boxed_goods_seed_json=estimate.seed,
        review_state="customer_confirm",
        review_reason=(
            f"We estimated about {estimate.box_count} boxes from your rooms "
            "and detected storage furniture -- please confirm or adjust."
        ),
    )
    return {"item_id": item_id, "created": True, "estimate": estimate}


def set_boxed_goods_count(
    conn: "sqlite3.Connection", item_id: int, count: int, volume_per_box_m3: float
) -> None:
    """Apply a customer's adjustment to the seeded boxed-goods count.

    Promotes out of `customer_confirm` like any other confirmed item, but
    never out of `staff_escalate` (boxed-goods lines aren't escalated today,
    kept here anyway so the rule stays uniform across all item kinds).
    """
    item = db.get_inventory_item(conn, item_id)
    updates = {"quantity": count, "unit_volume_m3": volume_per_box_m3}
    if item["review_state"] == "customer_confirm":
        updates["review_state"] = "auto_accept"
    db.update_inventory_item(conn, item_id, **updates)
    db.set_customer_confirmed(conn, item_id, True)


def confirm_item(conn: "sqlite3.Connection", item_id: int) -> None:
    """Customer confirms a flagged item's proposed number as-is.

    DESIGN.md SS5b's non-negotiable rule: confirming does not clear a staff
    escalation -- the two review paths are independent because the customer
    cannot assess whether a measurement is geometrically sound. Only a
    `customer_confirm` item promotes to `auto_accept`; a `staff_escalate`
    item only gets `customer_confirmed` set.
    """
    item = db.get_inventory_item(conn, item_id)
    db.set_customer_confirmed(conn, item_id, True)
    if item["review_state"] == "customer_confirm":
        db.update_inventory_item(conn, item_id, review_state="auto_accept")


def apply_customer_correction(
    conn: "sqlite3.Connection",
    item_id: int,
    *,
    width_m: float,
    height_m: float,
    depth_m: float,
) -> None:
    """Customer overrides a flagged item's proposed dimensions.

    `measurement_basis` flips from `measured`/`prior_assisted` to `declared`:
    the number moving forward is what the customer typed, so DESIGN.md SS5c's
    day-of surcharge (not the estimation-error margin) is what covers it if
    it's wrong. The original measured values are preserved under
    `provenance_json.customer_override` rather than overwritten -- SS5a's
    "provenance is mandatory" applies to what we measured, not just what the
    customer ended up confirming. Never clears a `staff_escalate` state (see
    `confirm_item`).
    """
    item = db.get_inventory_item(conn, item_id)
    provenance = dict(item.get("provenance_json") or {})
    provenance["customer_override"] = {
        "previous_width_m": item.get("width_m"),
        "previous_height_m": item.get("height_m"),
        "previous_depth_m": item.get("depth_m"),
        "previous_measurement_basis": item.get("measurement_basis"),
    }

    updates = {
        "width_m": width_m,
        "height_m": height_m,
        "depth_m": depth_m,
        "unit_volume_m3": width_m * height_m * depth_m,
        "measurement_basis": "declared",
        "provenance_json": provenance,
    }
    if item["review_state"] == "customer_confirm":
        updates["review_state"] = "auto_accept"
    db.update_inventory_item(conn, item_id, **updates)
    db.set_customer_confirmed(conn, item_id, True)


def add_declared_item(
    conn: "sqlite3.Connection",
    job_id: int,
    *,
    label: str,
    room_label: str | None,
    quantity: float,
    width_m: float,
    height_m: float,
    depth_m: float,
) -> int:
    """Add a customer-entered item the pipeline never saw (DESIGN.md SS5a:
    `declared` covers both boxed-goods lines and manually-entered objects).
    Auto-accepted -- the customer just typed this in, there is nothing left
    for them to confirm.
    """
    item_id = db.add_inventory_item(
        conn,
        job_id,
        label=label,
        measurement_basis="declared",
        room_label=room_label,
        quantity=quantity,
        width_m=width_m,
        height_m=height_m,
        depth_m=depth_m,
        unit_volume_m3=width_m * height_m * depth_m,
        review_state="auto_accept",
    )
    db.set_customer_confirmed(conn, item_id, True)
    return item_id


def review_summary(conn: "sqlite3.Connection", job_id: int) -> dict:
    """Counts for the review page's footer."""
    items = db.list_inventory_items(conn, job_id)
    return {
        "total_items": len(items),
        "auto_accept_count": sum(1 for i in items if i["review_state"] == "auto_accept"),
        "customer_confirm_count": sum(
            1 for i in items if i["review_state"] == "customer_confirm"
        ),
        "staff_escalate_count": sum(
            1 for i in items if i["review_state"] == "staff_escalate"
        ),
    }
