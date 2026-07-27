"""SQLite persistence layer for the intake -> quote -> booking workflow.

Schema and access functions only. Stays free of Streamlit/pipeline imports so
it can be exercised without the model stack (see `db_smoke_test.py`).

Every numeric knob seeded into `pricing_config` is a rule-of-thumb starting
point, not measured data -- see `DESIGN.md`'s Calibration section, which
expects these to be overridden by partner-company job records once available.
Margin is applied in exactly one place (`pricing_config.volume_margin_fraction`,
consumed by Build 3's `upper_bound_volume_m3()`); no other layer in this schema
may add a second margin, per `DESIGN.md` SS5c.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from config import DB_PATH


MEASUREMENT_BASES = ("measured", "prior_assisted", "declared")
REVIEW_STATES = ("auto_accept", "customer_confirm", "staff_escalate")
JOB_STATUSES = (
    "intake",
    "capture",
    "inventory_review",
    "quoted",
    "booked",
    "cancelled",
)
BOOKING_STATUSES = (
    "pending_staff_review",
    "confirmed",
    "needs_customer_clarification",
    "cancelled",
)

SCHEMA_VERSION = 1

_DEFAULT_PRICING_CONFIG = {
    "name": "Default (uncalibrated placeholder)",
    "currency": "HKD",
    "base_callout_fee": 800.0,
    "price_per_m3": 350.0,
    "minimum_charge": 1500.0,
    "volume_margin_fraction": 0.15,
    "floor_multiplier_per_level": 0.08,
    "lift_multiplier": 1.05,
    "parking_multiplier_per_10m": 0.03,
    "max_access_multiplier": 2.0,
    "boxed_goods_labour_multiplier": 1.25,
    "volume_per_box_m3": 0.11,
}

_INVENTORY_ITEM_UPDATABLE_COLUMNS = {
    "label",
    "room_label",
    "measurement_basis",
    "quantity",
    "width_m",
    "height_m",
    "depth_m",
    "unit_volume_m3",
    "prior_assisted_axes",
    "boxed_goods_seed_json",
    "detection_confidence",
    "point_count",
    "used_axis_aligned_fallback",
    "mask_touches_border",
    "shell_ratio",
    "implausible_dimension",
    "measurement_error",
    "review_state",
    "review_reason",
    "source_image_name",
    "provenance_json",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path is not None else DB_PATH
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def initialize(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS job (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            status TEXT NOT NULL DEFAULT 'intake'
                CHECK (status IN ('intake','capture','inventory_review','quoted','booked','cancelled')),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS intake (
            job_id INTEGER PRIMARY KEY REFERENCES job(id) ON DELETE CASCADE,
            contact_name TEXT NOT NULL,
            contact_email TEXT NOT NULL,
            contact_phone TEXT,
            origin_address TEXT NOT NULL,
            origin_floor INTEGER NOT NULL DEFAULT 0,
            origin_has_lift INTEGER NOT NULL DEFAULT 0 CHECK (origin_has_lift IN (0,1)),
            origin_parking_distance_m REAL NOT NULL DEFAULT 0,
            destination_address TEXT NOT NULL,
            destination_floor INTEGER NOT NULL DEFAULT 0,
            destination_has_lift INTEGER NOT NULL DEFAULT 0 CHECK (destination_has_lift IN (0,1)),
            destination_parking_distance_m REAL NOT NULL DEFAULT 0,
            room_count INTEGER NOT NULL DEFAULT 1,
            preferred_move_date TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS inventory_item (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL REFERENCES job(id) ON DELETE CASCADE,
            label TEXT NOT NULL,
            room_label TEXT,
            measurement_basis TEXT NOT NULL
                CHECK (measurement_basis IN ('measured','prior_assisted','declared')),
            is_boxed_goods INTEGER NOT NULL DEFAULT 0 CHECK (is_boxed_goods IN (0,1)),
            quantity REAL NOT NULL DEFAULT 1,

            width_m REAL,
            height_m REAL,
            depth_m REAL,
            unit_volume_m3 REAL,
            prior_assisted_axes TEXT,

            boxed_goods_seed_json TEXT,

            detection_confidence REAL CHECK (detection_confidence IS NULL OR (detection_confidence >= 0 AND detection_confidence <= 1)),
            point_count INTEGER,
            used_axis_aligned_fallback INTEGER NOT NULL DEFAULT 0 CHECK (used_axis_aligned_fallback IN (0,1)),
            mask_touches_border INTEGER NOT NULL DEFAULT 0 CHECK (mask_touches_border IN (0,1)),
            shell_ratio REAL,
            implausible_dimension INTEGER NOT NULL DEFAULT 0 CHECK (implausible_dimension IN (0,1)),
            measurement_error TEXT,

            review_state TEXT NOT NULL DEFAULT 'auto_accept'
                CHECK (review_state IN ('auto_accept','customer_confirm','staff_escalate')),
            review_reason TEXT,
            customer_confirmed INTEGER NOT NULL DEFAULT 0 CHECK (customer_confirmed IN (0,1)),

            source_image_name TEXT,
            provenance_json TEXT,

            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,

            CHECK (
                is_boxed_goods = 0
                OR (
                    measurement_basis = 'declared'
                    AND width_m IS NULL
                    AND height_m IS NULL
                    AND depth_m IS NULL
                )
            ),
            CHECK (measurement_basis <> 'measured' OR prior_assisted_axes IS NULL)
        );

        CREATE TABLE IF NOT EXISTS pricing_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            currency TEXT NOT NULL,
            base_callout_fee REAL NOT NULL,
            price_per_m3 REAL NOT NULL,
            minimum_charge REAL NOT NULL,
            volume_margin_fraction REAL NOT NULL CHECK (volume_margin_fraction >= 0 AND volume_margin_fraction <= 1),
            floor_multiplier_per_level REAL NOT NULL,
            lift_multiplier REAL NOT NULL,
            parking_multiplier_per_10m REAL NOT NULL,
            max_access_multiplier REAL NOT NULL,
            boxed_goods_labour_multiplier REAL NOT NULL,
            volume_per_box_m3 REAL NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
            created_at TEXT NOT NULL
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_pricing_config_one_active
            ON pricing_config (is_active)
            WHERE is_active = 1;

        CREATE TABLE IF NOT EXISTS quote (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL REFERENCES job(id) ON DELETE CASCADE,
            version INTEGER NOT NULL,
            pricing_config_id INTEGER NOT NULL REFERENCES pricing_config(id),
            total_volume_m3 REAL NOT NULL,
            upper_bound_volume_m3 REAL NOT NULL,
            volume_margin_fraction REAL NOT NULL,
            access_multiplier REAL NOT NULL,
            total_price REAL NOT NULL,
            recommended_truck TEXT,
            is_superseded INTEGER NOT NULL DEFAULT 0 CHECK (is_superseded IN (0,1)),
            created_at TEXT NOT NULL,
            UNIQUE (job_id, version)
        );

        CREATE TABLE IF NOT EXISTS quote_line (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quote_id INTEGER NOT NULL REFERENCES quote(id) ON DELETE CASCADE,
            inventory_item_id INTEGER NOT NULL REFERENCES inventory_item(id),
            measurement_basis TEXT NOT NULL
                CHECK (measurement_basis IN ('measured','prior_assisted','declared')),
            volume_m3 REAL NOT NULL,
            price_component REAL NOT NULL,
            surcharge_eligible INTEGER NOT NULL
                CHECK (surcharge_eligible IN (0,1)),
            CHECK (
                (surcharge_eligible = 1 AND measurement_basis = 'declared')
                OR (surcharge_eligible = 0 AND measurement_basis <> 'declared')
            )
        );

        CREATE TABLE IF NOT EXISTS booking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL REFERENCES job(id) ON DELETE CASCADE,
            quote_id INTEGER NOT NULL REFERENCES quote(id),
            status TEXT NOT NULL DEFAULT 'pending_staff_review'
                CHECK (status IN ('pending_staff_review','confirmed','needs_customer_clarification','cancelled')),
            customer_note TEXT,
            staff_note TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )
    conn.execute(f"PRAGMA user_version = {int(SCHEMA_VERSION)}")

    existing = conn.execute("SELECT COUNT(*) AS n FROM pricing_config").fetchone()
    if existing["n"] == 0:
        save_pricing_config(conn, _DEFAULT_PRICING_CONFIG)
    conn.commit()


# --------------------------------------------------------------------------
# Job
# --------------------------------------------------------------------------


def create_job(conn: sqlite3.Connection) -> int:
    now = _now()
    cursor = conn.execute(
        "INSERT INTO job (status, created_at, updated_at) VALUES ('intake', ?, ?)",
        (now, now),
    )
    conn.commit()
    return int(cursor.lastrowid)


def get_job(conn: sqlite3.Connection, job_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM job WHERE id = ?", (job_id,)).fetchone()
    return dict(row) if row else None


def set_job_status(conn: sqlite3.Connection, job_id: int, status: str) -> None:
    if status not in JOB_STATUSES:
        raise ValueError(f"Unknown job status: {status!r}")
    conn.execute(
        "UPDATE job SET status = ?, updated_at = ? WHERE id = ?",
        (status, _now(), job_id),
    )
    conn.commit()


# --------------------------------------------------------------------------
# Intake
# --------------------------------------------------------------------------


def save_intake(conn: sqlite3.Connection, job_id: int, **fields) -> None:
    now = _now()
    existing = conn.execute(
        "SELECT job_id FROM intake WHERE job_id = ?", (job_id,)
    ).fetchone()

    columns = [
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
    ]
    values = {column: fields.get(column) for column in columns}

    if existing is None:
        placeholders = ", ".join(["?"] * (len(columns) + 3))
        conn.execute(
            f"INSERT INTO intake (job_id, {', '.join(columns)}, created_at, updated_at) "
            f"VALUES ({placeholders})",
            (job_id, *(values[c] for c in columns), now, now),
        )
    else:
        assignments = ", ".join(f"{c} = ?" for c in columns)
        conn.execute(
            f"UPDATE intake SET {assignments}, updated_at = ? WHERE job_id = ?",
            (*(values[c] for c in columns), now, job_id),
        )
    conn.commit()


def get_intake(conn: sqlite3.Connection, job_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM intake WHERE job_id = ?", (job_id,)).fetchone()
    return dict(row) if row else None


# --------------------------------------------------------------------------
# Inventory
# --------------------------------------------------------------------------


def add_inventory_item(
    conn: sqlite3.Connection,
    job_id: int,
    *,
    label: str,
    measurement_basis: str,
    quantity: float = 1,
    room_label: str | None = None,
    width_m: float | None = None,
    height_m: float | None = None,
    depth_m: float | None = None,
    unit_volume_m3: float | None = None,
    prior_assisted_axes: list[str] | None = None,
    is_boxed_goods: bool = False,
    boxed_goods_seed_json: dict | None = None,
    detection_confidence: float | None = None,
    point_count: int | None = None,
    used_axis_aligned_fallback: bool = False,
    mask_touches_border: bool = False,
    shell_ratio: float | None = None,
    implausible_dimension: bool = False,
    measurement_error: str | None = None,
    review_state: str = "auto_accept",
    review_reason: str | None = None,
    source_image_name: str | None = None,
    provenance_json: dict | list | None = None,
) -> int:
    if measurement_basis not in MEASUREMENT_BASES:
        raise ValueError(f"Unknown measurement_basis: {measurement_basis!r}")
    if review_state not in REVIEW_STATES:
        raise ValueError(f"Unknown review_state: {review_state!r}")

    now = _now()
    cursor = conn.execute(
        """
        INSERT INTO inventory_item (
            job_id, label, room_label, measurement_basis, is_boxed_goods, quantity,
            width_m, height_m, depth_m, unit_volume_m3, prior_assisted_axes,
            boxed_goods_seed_json,
            detection_confidence, point_count, used_axis_aligned_fallback,
            mask_touches_border, shell_ratio, implausible_dimension, measurement_error,
            review_state, review_reason,
            source_image_name, provenance_json,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            job_id,
            label,
            room_label,
            measurement_basis,
            int(is_boxed_goods),
            quantity,
            width_m,
            height_m,
            depth_m,
            unit_volume_m3,
            json.dumps(prior_assisted_axes) if prior_assisted_axes is not None else None,
            json.dumps(boxed_goods_seed_json) if boxed_goods_seed_json is not None else None,
            detection_confidence,
            point_count,
            int(used_axis_aligned_fallback),
            int(mask_touches_border),
            shell_ratio,
            int(implausible_dimension),
            measurement_error,
            review_state,
            review_reason,
            source_image_name,
            json.dumps(provenance_json) if provenance_json is not None else None,
            now,
            now,
        ),
    )
    conn.commit()
    return int(cursor.lastrowid)


def add_boxed_goods_item(
    conn: sqlite3.Connection,
    job_id: int,
    *,
    label: str,
    quantity: float,
    unit_volume_m3: float,
    boxed_goods_seed_json: dict,
    room_label: str | None = None,
    review_state: str = "auto_accept",
    review_reason: str | None = None,
) -> int:
    return add_inventory_item(
        conn,
        job_id,
        label=label,
        measurement_basis="declared",
        quantity=quantity,
        room_label=room_label,
        unit_volume_m3=unit_volume_m3,
        is_boxed_goods=True,
        boxed_goods_seed_json=boxed_goods_seed_json,
        review_state=review_state,
        review_reason=review_reason,
    )


def _inventory_row_to_dict(row: sqlite3.Row) -> dict:
    item = dict(row)
    for json_field in ("prior_assisted_axes", "boxed_goods_seed_json", "provenance_json"):
        if item.get(json_field):
            item[json_field] = json.loads(item[json_field])
    return item


def list_inventory_items(conn: sqlite3.Connection, job_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM inventory_item WHERE job_id = ? ORDER BY id", (job_id,)
    ).fetchall()
    return [_inventory_row_to_dict(row) for row in rows]


def get_inventory_item(conn: sqlite3.Connection, item_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM inventory_item WHERE id = ?", (item_id,)
    ).fetchone()
    return _inventory_row_to_dict(row) if row else None


def update_inventory_item(conn: sqlite3.Connection, item_id: int, **fields) -> None:
    unknown = set(fields) - _INVENTORY_ITEM_UPDATABLE_COLUMNS
    if unknown:
        raise ValueError(f"Cannot update columns: {sorted(unknown)}")
    if not fields:
        return

    json_columns = {"prior_assisted_axes", "boxed_goods_seed_json", "provenance_json"}
    assignments = []
    values = []
    for column, value in fields.items():
        assignments.append(f"{column} = ?")
        if column in json_columns and value is not None:
            values.append(json.dumps(value))
        else:
            values.append(value)

    values.append(_now())
    values.append(item_id)
    conn.execute(
        f"UPDATE inventory_item SET {', '.join(assignments)}, updated_at = ? WHERE id = ?",
        values,
    )
    conn.commit()


def set_customer_confirmed(conn: sqlite3.Connection, item_id: int, confirmed: bool = True) -> None:
    conn.execute(
        "UPDATE inventory_item SET customer_confirmed = ?, updated_at = ? WHERE id = ?",
        (int(confirmed), _now(), item_id),
    )
    conn.commit()


def delete_inventory_item(conn: sqlite3.Connection, item_id: int) -> None:
    conn.execute("DELETE FROM inventory_item WHERE id = ?", (item_id,))
    conn.commit()


# --------------------------------------------------------------------------
# Pricing config
# --------------------------------------------------------------------------


def get_active_pricing_config(conn: sqlite3.Connection) -> dict | None:
    row = conn.execute(
        "SELECT * FROM pricing_config WHERE is_active = 1"
    ).fetchone()
    return dict(row) if row else None


def save_pricing_config(conn: sqlite3.Connection, config: dict) -> int:
    conn.execute("UPDATE pricing_config SET is_active = 0 WHERE is_active = 1")
    cursor = conn.execute(
        """
        INSERT INTO pricing_config (
            name, currency, base_callout_fee, price_per_m3, minimum_charge,
            volume_margin_fraction, floor_multiplier_per_level, lift_multiplier,
            parking_multiplier_per_10m, max_access_multiplier,
            boxed_goods_labour_multiplier, volume_per_box_m3,
            is_active, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
        """,
        (
            config["name"],
            config["currency"],
            config["base_callout_fee"],
            config["price_per_m3"],
            config["minimum_charge"],
            config["volume_margin_fraction"],
            config["floor_multiplier_per_level"],
            config["lift_multiplier"],
            config["parking_multiplier_per_10m"],
            config["max_access_multiplier"],
            config["boxed_goods_labour_multiplier"],
            config["volume_per_box_m3"],
            _now(),
        ),
    )
    conn.commit()
    return int(cursor.lastrowid)


# --------------------------------------------------------------------------
# Quotes
# --------------------------------------------------------------------------


def create_quote(
    conn: sqlite3.Connection,
    job_id: int,
    *,
    pricing_config_id: int,
    total_volume_m3: float,
    upper_bound_volume_m3: float,
    volume_margin_fraction: float,
    access_multiplier: float,
    total_price: float,
    recommended_truck: str | None,
    lines: list[dict],
) -> int:
    """Insert a new quote version, superseding any prior active quote for this job.

    Never mutates a previous quote row (`DESIGN.md` SS5c). `lines` items need
    `inventory_item_id`, `measurement_basis`, `volume_m3`, `price_component`.
    """
    previous_max = conn.execute(
        "SELECT COALESCE(MAX(version), 0) AS max_version FROM quote WHERE job_id = ?",
        (job_id,),
    ).fetchone()["max_version"]
    next_version = previous_max + 1

    conn.execute(
        "UPDATE quote SET is_superseded = 1 WHERE job_id = ? AND is_superseded = 0",
        (job_id,),
    )

    now = _now()
    cursor = conn.execute(
        """
        INSERT INTO quote (
            job_id, version, pricing_config_id, total_volume_m3,
            upper_bound_volume_m3, volume_margin_fraction, access_multiplier,
            total_price, recommended_truck, is_superseded, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
        """,
        (
            job_id,
            next_version,
            pricing_config_id,
            total_volume_m3,
            upper_bound_volume_m3,
            volume_margin_fraction,
            access_multiplier,
            total_price,
            recommended_truck,
            now,
        ),
    )
    quote_id = int(cursor.lastrowid)

    for line in lines:
        measurement_basis = line["measurement_basis"]
        if measurement_basis not in MEASUREMENT_BASES:
            raise ValueError(f"Unknown measurement_basis: {measurement_basis!r}")
        conn.execute(
            """
            INSERT INTO quote_line (
                quote_id, inventory_item_id, measurement_basis, volume_m3,
                price_component, surcharge_eligible
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                quote_id,
                line["inventory_item_id"],
                measurement_basis,
                line["volume_m3"],
                line["price_component"],
                int(measurement_basis == "declared"),
            ),
        )

    conn.commit()
    return quote_id


def get_active_quote(conn: sqlite3.Connection, job_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM quote WHERE job_id = ? AND is_superseded = 0", (job_id,)
    ).fetchone()
    return dict(row) if row else None


def list_quotes(conn: sqlite3.Connection, job_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM quote WHERE job_id = ? ORDER BY version", (job_id,)
    ).fetchall()
    return [dict(row) for row in rows]


def get_quote_lines(conn: sqlite3.Connection, quote_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM quote_line WHERE quote_id = ?", (quote_id,)
    ).fetchall()
    return [dict(row) for row in rows]


# --------------------------------------------------------------------------
# Bookings
# --------------------------------------------------------------------------


def create_booking(
    conn: sqlite3.Connection,
    job_id: int,
    quote_id: int,
    *,
    customer_note: str | None = None,
) -> int:
    now = _now()
    cursor = conn.execute(
        """
        INSERT INTO booking (job_id, quote_id, status, customer_note, created_at, updated_at)
        VALUES (?, ?, 'pending_staff_review', ?, ?, ?)
        """,
        (job_id, quote_id, customer_note, now, now),
    )
    conn.commit()
    return int(cursor.lastrowid)


def update_booking_status(
    conn: sqlite3.Connection,
    booking_id: int,
    status: str,
    *,
    staff_note: str | None = None,
) -> None:
    if status not in BOOKING_STATUSES:
        raise ValueError(f"Unknown booking status: {status!r}")
    conn.execute(
        "UPDATE booking SET status = ?, staff_note = COALESCE(?, staff_note), updated_at = ? WHERE id = ?",
        (status, staff_note, _now(), booking_id),
    )
    conn.commit()


def list_bookings(conn: sqlite3.Connection, status: str | None = None) -> list[dict]:
    query = """
        SELECT booking.*, job.status AS job_status, quote.total_price, quote.recommended_truck
        FROM booking
        JOIN job ON job.id = booking.job_id
        JOIN quote ON quote.id = booking.quote_id
    """
    params: tuple = ()
    if status is not None:
        query += " WHERE booking.status = ?"
        params = (status,)
    query += " ORDER BY booking.created_at DESC"
    rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]
