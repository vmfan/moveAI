from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from backend import deps
from backend.schemas import BoxedGoodsCountIn, CorrectionIn, DeclaredItemIn

import db  # noqa: E402
import inventory_sync  # noqa: E402

router = APIRouter(prefix="/api/jobs/{job_id}/inventory", tags=["inventory"])


def _require_config(conn: sqlite3.Connection) -> dict:
    config = db.get_active_pricing_config(conn)
    if config is None:
        raise HTTPException(status_code=409, detail="No active pricing configuration.")
    return config


@router.get("")
def list_inventory(
    job: dict = Depends(deps.get_job_or_404),
    conn: sqlite3.Connection = Depends(deps.get_conn),
) -> dict:
    intake = db.get_intake(conn, job["id"])
    if intake is not None:
        config = _require_config(conn)
        inventory_sync.seed_boxed_goods(
            conn,
            job["id"],
            room_count=intake["room_count"],
            volume_per_box_m3=config["volume_per_box_m3"],
        )
    return {
        "items": db.list_inventory_items(conn, job["id"]),
        "summary": inventory_sync.review_summary(conn, job["id"]),
    }


@router.post("/declared")
def add_declared_item(
    payload: DeclaredItemIn,
    job: dict = Depends(deps.get_job_or_404),
    conn: sqlite3.Connection = Depends(deps.get_conn),
) -> dict:
    item_id = inventory_sync.add_declared_item(conn, job["id"], **payload.model_dump())
    if job["status"] == "capture":
        db.set_job_status(conn, job["id"], "inventory_review")
    return db.get_inventory_item(conn, item_id)


@router.post("/{item_id}/confirm")
def confirm_item(
    item_id: int,
    job: dict = Depends(deps.get_job_or_404),
    conn: sqlite3.Connection = Depends(deps.get_conn),
) -> dict:
    item = db.get_inventory_item(conn, item_id)
    if item is None or item["job_id"] != job["id"]:
        raise HTTPException(status_code=404, detail=f"No inventory item with id {item_id!r}")
    inventory_sync.confirm_item(conn, item_id)
    return db.get_inventory_item(conn, item_id)


@router.post("/{item_id}/correct")
def correct_item(
    item_id: int,
    payload: CorrectionIn,
    job: dict = Depends(deps.get_job_or_404),
    conn: sqlite3.Connection = Depends(deps.get_conn),
) -> dict:
    item = db.get_inventory_item(conn, item_id)
    if item is None or item["job_id"] != job["id"]:
        raise HTTPException(status_code=404, detail=f"No inventory item with id {item_id!r}")
    inventory_sync.apply_customer_correction(conn, item_id, **payload.model_dump())
    return db.get_inventory_item(conn, item_id)


@router.post("/boxed-goods/count")
def set_boxed_goods_count(
    payload: BoxedGoodsCountIn,
    job: dict = Depends(deps.get_job_or_404),
    conn: sqlite3.Connection = Depends(deps.get_conn),
) -> dict:
    item = db.get_inventory_item(conn, payload.item_id)
    if item is None or item["job_id"] != job["id"] or not item["is_boxed_goods"]:
        raise HTTPException(
            status_code=404, detail=f"No boxed-goods item with id {payload.item_id!r}"
        )
    config = _require_config(conn)
    inventory_sync.set_boxed_goods_count(
        conn, payload.item_id, payload.count, config["volume_per_box_m3"]
    )
    return db.get_inventory_item(conn, payload.item_id)


@router.delete("/{item_id}")
def delete_item(
    item_id: int,
    job: dict = Depends(deps.get_job_or_404),
    conn: sqlite3.Connection = Depends(deps.get_conn),
) -> dict:
    item = db.get_inventory_item(conn, item_id)
    if item is None or item["job_id"] != job["id"]:
        raise HTTPException(status_code=404, detail=f"No inventory item with id {item_id!r}")
    db.delete_inventory_item(conn, item_id)
    return {"deleted": True, "item_id": item_id}
