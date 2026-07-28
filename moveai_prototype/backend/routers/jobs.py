from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from backend import deps

import db  # noqa: E402

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.post("")
def create_job(conn: sqlite3.Connection = Depends(deps.get_conn)) -> dict:
    job_id = db.create_job(conn)
    return db.get_job(conn, job_id)


@router.get("/{job_id}")
def get_job(job: dict = Depends(deps.get_job_or_404)) -> dict:
    return job
