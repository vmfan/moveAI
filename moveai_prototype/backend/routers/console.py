from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from backend import deps
from backend.schemas import StaffDecisionIn

import booking_sync  # noqa: E402
import db  # noqa: E402

router = APIRouter(prefix="/api/console", tags=["console"])


@router.get("/bookings")
def list_bookings(
    status: str | None = None,
    conn: sqlite3.Connection = Depends(deps.get_conn),
) -> list[dict]:
    return booking_sync.console_rows(conn, status=status)


@router.post("/bookings/{booking_id}/decision")
def decide_booking(
    booking_id: int,
    payload: StaffDecisionIn,
    conn: sqlite3.Connection = Depends(deps.get_conn),
) -> dict:
    if db.get_booking(conn, booking_id) is None:
        raise HTTPException(status_code=404, detail=f"No booking with id {booking_id!r}")
    try:
        booking_sync.apply_staff_decision(
            conn, booking_id, payload.status, staff_note=payload.staff_note
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return db.get_booking(conn, booking_id)
