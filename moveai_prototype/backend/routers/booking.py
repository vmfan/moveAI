from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from backend import deps
from backend.routers.quote import _build_fresh
from backend.schemas import BookingSubmitIn, ResubmitIn

import booking_sync  # noqa: E402
import db  # noqa: E402

router = APIRouter(prefix="/api/jobs/{job_id}/booking", tags=["booking"])


def _stored_quote_and_lines(conn: sqlite3.Connection, job_id: int) -> tuple[dict | None, list[dict]]:
    stored = db.get_active_quote(conn, job_id)
    stored_lines = db.get_quote_lines(conn, stored["id"]) if stored else []
    return stored, stored_lines


@router.get("")
def get_booking_status(
    job: dict = Depends(deps.get_job_or_404),
    conn: sqlite3.Connection = Depends(deps.get_conn),
) -> dict:
    stored, stored_lines = _stored_quote_and_lines(conn, job["id"])
    try:
        fresh, _items = _build_fresh(conn, job["id"])
        blockers = booking_sync.booking_blockers(stored, stored_lines, fresh)
    except HTTPException:
        blockers = ["No quote has been generated yet."]
    return {
        "booking": booking_sync.active_booking(conn, job["id"]),
        "blockers": blockers,
    }


@router.post("/submit")
def submit_booking(
    payload: BookingSubmitIn,
    job: dict = Depends(deps.get_job_or_404),
    conn: sqlite3.Connection = Depends(deps.get_conn),
) -> dict:
    stored, stored_lines = _stored_quote_and_lines(conn, job["id"])
    fresh, _items = _build_fresh(conn, job["id"])
    blockers = booking_sync.booking_blockers(stored, stored_lines, fresh)
    if blockers:
        raise HTTPException(status_code=409, detail=blockers)

    booking_id, created = booking_sync.submit_booking(
        conn, job["id"], stored["id"], customer_note=payload.customer_note
    )
    return {"booking": db.get_booking(conn, booking_id), "created": created}


@router.post("/resubmit")
def resubmit_booking(
    payload: ResubmitIn,
    job: dict = Depends(deps.get_job_or_404),
    conn: sqlite3.Connection = Depends(deps.get_conn),
) -> dict:
    booking = booking_sync.active_booking(conn, job["id"])
    if booking is None:
        raise HTTPException(status_code=404, detail="No booking exists for this job.")
    try:
        booking_sync.resubmit_booking(
            conn, booking["id"], customer_note=payload.customer_note
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return db.get_booking(conn, booking["id"])
