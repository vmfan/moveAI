"""Pydantic request-body models for the FastAPI routers
(IMPLEMENTATION_ROADMAP.md Build 8).

Response bodies are returned as plain dicts (the shape `db.py`/`*_sync.py`
already produce) rather than modeled here -- routers stay thin wrappers, not
a second schema layer duplicating what the sync modules already return.
"""

from __future__ import annotations

from pydantic import BaseModel


class IntakeIn(BaseModel):
    contact_name: str
    contact_email: str
    contact_phone: str | None = None
    origin_address: str
    origin_floor: int = 0
    origin_has_lift: bool = False
    origin_parking_distance_m: float = 0.0
    destination_address: str
    destination_floor: int = 0
    destination_has_lift: bool = False
    destination_parking_distance_m: float = 0.0
    room_count: int = 1
    preferred_move_date: str | None = None


class DeclaredItemIn(BaseModel):
    label: str
    room_label: str | None = None
    quantity: float = 1
    width_m: float
    height_m: float
    depth_m: float


class CorrectionIn(BaseModel):
    width_m: float
    height_m: float
    depth_m: float


class BoxedGoodsCountIn(BaseModel):
    item_id: int
    count: int


class BookingSubmitIn(BaseModel):
    customer_note: str | None = None


class ResubmitIn(BaseModel):
    customer_note: str | None = None


class StaffDecisionIn(BaseModel):
    status: str
    staff_note: str | None = None
