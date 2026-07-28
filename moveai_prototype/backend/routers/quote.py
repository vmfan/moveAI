from __future__ import annotations

import sqlite3
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException

from backend import deps

import db  # noqa: E402
import pricing  # noqa: E402
import quote_sync  # noqa: E402

router = APIRouter(prefix="/api/jobs/{job_id}/quote", tags=["quote"])


def _build_fresh(conn: sqlite3.Connection, job_id: int) -> tuple["pricing.Quote", list[dict]]:
    intake = db.get_intake(conn, job_id)
    if intake is None:
        raise HTTPException(status_code=409, detail="Intake must be completed before quoting.")
    config = db.get_active_pricing_config(conn)
    if config is None:
        raise HTTPException(status_code=409, detail="No active pricing configuration.")
    items = db.list_inventory_items(conn, job_id)
    if not items:
        raise HTTPException(status_code=409, detail="No inventory items yet.")
    return pricing.build_quote(items, intake, config), items


def _payload(quote: "pricing.Quote", items: list[dict], *, version: int | None, stale: bool) -> dict:
    return {
        "quote": asdict(quote),
        "version": version,
        "stale": stale,
        "lines": quote_sync.quote_view_rows(items, quote),
        "staff_review_reasons": quote_sync.staff_review_reasons(items, quote),
    }


@router.get("")
def get_quote(
    job: dict = Depends(deps.get_job_or_404),
    conn: sqlite3.Connection = Depends(deps.get_conn),
) -> dict:
    fresh, items = _build_fresh(conn, job["id"])
    config = db.get_active_pricing_config(conn)
    stored = db.get_active_quote(conn, job["id"])

    if stored is None:
        quote_sync.persist_quote(conn, job["id"], fresh, pricing_config_id=config["id"])
        stored = db.get_active_quote(conn, job["id"])
        return _payload(fresh, items, version=stored["version"], stale=False)

    stored_lines = db.get_quote_lines(conn, stored["id"])
    if quote_sync.quote_matches(stored, stored_lines, fresh):
        return _payload(fresh, items, version=stored["version"], stale=False)

    return _payload(fresh, items, version=stored["version"], stale=True)


@router.post("/regenerate")
def regenerate_quote(
    job: dict = Depends(deps.get_job_or_404),
    conn: sqlite3.Connection = Depends(deps.get_conn),
) -> dict:
    fresh, items = _build_fresh(conn, job["id"])
    config = db.get_active_pricing_config(conn)
    quote_sync.persist_quote(conn, job["id"], fresh, pricing_config_id=config["id"])
    stored = db.get_active_quote(conn, job["id"])
    return _payload(fresh, items, version=stored["version"], stale=False)


@router.get("/versions")
def list_versions(
    job: dict = Depends(deps.get_job_or_404),
    conn: sqlite3.Connection = Depends(deps.get_conn),
) -> list[dict]:
    return db.list_quotes(conn, job["id"])
