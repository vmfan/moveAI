from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from backend import deps
from backend.schemas import IntakeIn

import db  # noqa: E402
import inventory_sync  # noqa: E402

router = APIRouter(prefix="/api/jobs/{job_id}/intake", tags=["intake"])


@router.put("")
def save_intake(
    payload: IntakeIn,
    job: dict = Depends(deps.get_job_or_404),
    conn: sqlite3.Connection = Depends(deps.get_conn),
) -> dict:
    fields = payload.model_dump()
    errors = inventory_sync.intake_validation_errors(fields)
    if errors:
        raise HTTPException(status_code=422, detail=errors)

    db.save_intake(conn, job["id"], **fields)
    if job["status"] == "intake":
        db.set_job_status(conn, job["id"], "capture")
    return db.get_intake(conn, job["id"])


@router.get("")
def get_intake(
    job: dict = Depends(deps.get_job_or_404),
    conn: sqlite3.Connection = Depends(deps.get_conn),
) -> dict:
    intake = db.get_intake(conn, job["id"])
    if intake is None:
        raise HTTPException(status_code=404, detail="No intake saved for this job yet.")
    return intake
