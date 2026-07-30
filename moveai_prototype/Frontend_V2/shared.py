from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).parent / "data"
UPLOAD_DIR = Path(__file__).parent / "uploads"
REQUESTS_FILE = DATA_DIR / "requests.json"

DATA_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)


FURNITURE_CATALOG = {
    "Sofa, 2-seater": {"volume_m3": 1.8, "base_price": 85},
    "Sofa, 3-seater": {"volume_m3": 2.6, "base_price": 120},
    "Armchair": {"volume_m3": 0.8, "base_price": 42},
    "Dining table": {"volume_m3": 1.3, "base_price": 65},
    "Dining chair": {"volume_m3": 0.25, "base_price": 14},
    "Coffee table": {"volume_m3": 0.45, "base_price": 28},
    "Bed, single": {"volume_m3": 1.5, "base_price": 75},
    "Bed, double": {"volume_m3": 2.4, "base_price": 110},
    "Wardrobe, small": {"volume_m3": 1.4, "base_price": 72},
    "Wardrobe, large": {"volume_m3": 2.3, "base_price": 115},
    "Desk": {"volume_m3": 0.9, "base_price": 45},
    "Office chair": {"volume_m3": 0.35, "base_price": 18},
    "Bookshelf": {"volume_m3": 0.75, "base_price": 39},
    "TV": {"volume_m3": 0.18, "base_price": 16},
    "TV cabinet": {"volume_m3": 0.65, "base_price": 34},
    "Washing machine": {"volume_m3": 0.45, "base_price": 32},
    "Refrigerator": {"volume_m3": 0.9, "base_price": 55},
    "Moving box": {"volume_m3": 0.08, "base_price": 5},
    "Other item": {"volume_m3": 0.5, "base_price": 30},
}


def load_requests() -> list[dict[str, Any]]:
    if not REQUESTS_FILE.exists():
        REQUESTS_FILE.write_text("[]", encoding="utf-8")
        return []

    try:
        return json.loads(REQUESTS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def save_requests(requests: list[dict[str, Any]]) -> None:
    REQUESTS_FILE.write_text(
        json.dumps(requests, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def create_request(payload: dict[str, Any]) -> str:
    requests = load_requests()
    request_id = f"MV-{datetime.now():%Y%m%d}-{uuid.uuid4().hex[:6].upper()}"

    payload = {
        **payload,
        "request_id": request_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "status": "Pending",
        "administrator_note": "",
    }

    requests.append(payload)
    save_requests(requests)
    return request_id


def update_request(
    request_id: str,
    *,
    status: str,
    administrator_note: str = "",
) -> bool:
    requests = load_requests()
    changed = False

    for request in requests:
        if request.get("request_id") == request_id:
            request["status"] = status
            request["administrator_note"] = administrator_note
            request["reviewed_at"] = datetime.now().isoformat(timespec="seconds")
            changed = True
            break

    if changed:
        save_requests(requests)

    return changed


def save_uploaded_files(uploaded_files: list[Any]) -> list[str]:
    stored_paths: list[str] = []

    for uploaded_file in uploaded_files:
        safe_name = Path(uploaded_file.name).name
        unique_name = f"{uuid.uuid4().hex[:8]}_{safe_name}"
        target_path = UPLOAD_DIR / unique_name
        target_path.write_bytes(uploaded_file.getbuffer())
        stored_paths.append(str(target_path))

    return stored_paths


def estimate_quote(
    furniture: list[dict[str, Any]],
    pickup_floor: int,
    pickup_lift: bool,
    destination_floor: int,
    destination_lift: bool,
) -> dict[str, float]:
    total_volume = sum(
        float(item["volume_m3"]) * int(item["quantity"])
        for item in furniture
    )
    furniture_price = sum(
        float(item["unit_price"]) * int(item["quantity"])
        for item in furniture
    )

    access_surcharge = 0.0

    if not pickup_lift:
        access_surcharge += max(pickup_floor, 0) * 18
    if not destination_lift:
        access_surcharge += max(destination_floor, 0) * 18

    base_transport = 120 + total_volume * 28
    subtotal = furniture_price + access_surcharge + base_transport
    service_fee = subtotal * 0.08
    estimated_total = subtotal + service_fee

    return {
        "total_volume_m3": round(total_volume, 2),
        "furniture_price": round(furniture_price, 2),
        "access_surcharge": round(access_surcharge, 2),
        "base_transport": round(base_transport, 2),
        "service_fee": round(service_fee, 2),
        "estimated_total": round(estimated_total, 2),
    }


def simulate_furniture_detection(file_count: int) -> list[dict[str, Any]]:
    simulated = [
        ("Sofa, 3-seater", 1),
        ("Dining table", 1),
        ("Dining chair", 4),
        ("Bed, double", 1),
        ("Wardrobe, large", 1),
        ("Moving box", max(4, file_count * 3)),
    ]

    detected = []
    for item_name, quantity in simulated:
        item = FURNITURE_CATALOG[item_name]
        detected.append(
            {
                "name": item_name,
                "quantity": quantity,
                "volume_m3": item["volume_m3"],
                "unit_price": item["base_price"],
                "source": "AI detected",
            }
        )

    return detected
