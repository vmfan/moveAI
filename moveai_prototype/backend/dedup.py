"""Cross-image dedup + room labeling, run automatically after a batch
capture finishes (IMPLEMENTATION_ROADMAP.md multi-image build).

Sends one overlay PNG per captured image -- reusing the same
`serialization.overlay_png()`/`render_detection_overlay()` already used by
the `overlay.png` endpoint, numbered boxes matching item indices -- plus
each image's item list, to the HKUST-hosted `qwen-vl` vision model via
`reasoning_client`. Asks it to (a) group item indices that are the same
physical object photographed more than once, and (b) infer a room label per
image where the customer didn't type one.

Duplicate groups are resolved by keeping the item with the highest
detection_confidence and deleting the rest via the existing
`db.delete_inventory_item` -- the same delete used by
`inventory_sync.persist_capture()`'s own re-capture-replaces-rows behavior,
so downstream readers (quote/booking) see deleted items disappear the same
way they already do today. The deleted items' source images are folded into
the kept item's `provenance_json.frames` list, which `persist_capture()`
already writes as a list (currently always length 1) in anticipation of
exactly this.

A failed/unreachable model call must not roll back or block the capture
that already persisted; callers should catch `ReasoningClientError` and
surface it as a soft warning instead of failing the request.
"""

from __future__ import annotations

import json
import sqlite3
from typing import TYPE_CHECKING

import db
from backend import reasoning_client, serialization

if TYPE_CHECKING:
    from pipeline import PipelineResult

SYSTEM_PROMPT = (
    "You are helping merge furniture inventory detected across multiple "
    "photos of the same house move job. Each photo is provided as an image "
    "with numbered boxes drawn around detected items, immediately followed "
    "by a JSON list describing that photo's items (by the same numbers). "
    "Some items may be the same physical object photographed from a "
    "different angle or distance -- group only items you are confident are "
    "the same physical object. Items that merely look similar (e.g. two "
    "matching dining chairs, two identical boxes) are NOT duplicates and "
    "must stay ungrouped. Also infer a short room label (e.g. "
    "'Living room', 'Bedroom 1', 'Kitchen') for each photo whose item list "
    "has \"room_label\": null; leave alone (omit from room_labels) any "
    "photo that already has a non-null room_label.\n\n"
    "Respond with only a JSON object of this exact shape:\n"
    '{"duplicate_groups": [[{"image_name": "...", "item_index": 1}, '
    '{"image_name": "...", "item_index": 2}]], '
    '"room_labels": {"image_name": "room label"}}\n'
    "duplicate_groups is a list of groups of 2+ items each; every item you "
    "don't mention is assumed to be a unique physical object."
)


class CaptureBatchImage:
    """One image's worth of state from a just-persisted batch capture,
    passed into `run_dedup_and_labeling` so it can match the model's
    (image_name, item_index) references back to real inventory_item rows
    without re-deriving DB insertion order."""

    __slots__ = ("image_name", "result", "measured_item_ids", "room_label")

    def __init__(
        self,
        image_name: str,
        result: "PipelineResult",
        measured_item_ids: list[int],
        room_label: str | None,
    ) -> None:
        self.image_name = image_name
        self.result = result
        self.measured_item_ids = measured_item_ids
        self.room_label = room_label


def _build_prompt_text(captures: list[CaptureBatchImage]) -> str:
    sections = []
    for capture in captures:
        items = [
            {
                "item_index": index,
                "label": measurement.label,
                "width_m": round(measurement.width_m, 3),
                "height_m": round(measurement.height_m, 3),
                "depth_m": round(measurement.depth_m, 3),
                "detection_confidence": round(measurement.detection_score, 3),
            }
            for index, measurement in enumerate(capture.result.measurements, start=1)
        ]
        sections.append(
            {
                "image_name": capture.image_name,
                "room_label": capture.room_label,
                "items": items,
            }
        )
    return json.dumps({"photos": sections})


def run_dedup_and_labeling(
    conn: sqlite3.Connection,
    job_id: int,
    captures: list[CaptureBatchImage],
) -> dict:
    """Runs the cross-image merge + room-labeling pass for a just-persisted
    batch capture and applies the result to the DB.

    Returns a summary dict: `duplicates_removed` (list of {kept_item_id,
    removed_item_ids}) and `room_labels_assigned` (image_name -> label).
    Raises `reasoning_client.ReasoningClientError` on any model-call
    failure -- callers decide how to degrade.
    """
    if len(captures) < 2:
        # Nothing to cross-reference with a single image; still apply a
        # room label if the model would otherwise be asked to infer one,
        # but skip the network round trip entirely.
        return {"duplicates_removed": [], "room_labels_assigned": {}}

    overlays = [serialization.overlay_png(capture.result) for capture in captures]
    user_text = _build_prompt_text(captures)

    response = reasoning_client.ask_vision_json(
        system_prompt=SYSTEM_PROMPT,
        user_text=user_text,
        images=overlays,
    )

    by_image = {capture.image_name: capture for capture in captures}
    duplicates_removed: list[dict] = []

    for group in response.get("duplicate_groups", []):
        resolved: list[tuple[int, float]] = []  # (item_id, detection_confidence)
        for ref in group:
            image_name = ref.get("image_name")
            item_index = ref.get("item_index")
            capture = by_image.get(image_name)
            if capture is None or not isinstance(item_index, int):
                continue
            if item_index < 1 or item_index > len(capture.measured_item_ids):
                continue
            item_id = capture.measured_item_ids[item_index - 1]
            confidence = capture.result.measurements[item_index - 1].detection_score
            resolved.append((item_id, confidence))

        if len(resolved) < 2:
            continue

        resolved.sort(key=lambda pair: pair[1], reverse=True)
        keeper_id = resolved[0][0]
        removed_ids = [item_id for item_id, _ in resolved[1:]]

        keeper = db.get_inventory_item(conn, keeper_id)
        if keeper is None:
            continue
        frames = list((keeper.get("provenance_json") or {}).get("frames") or [])
        seen_images = {frame.get("image_name") for frame in frames}
        for item_id in removed_ids:
            removed_item = db.get_inventory_item(conn, item_id)
            if removed_item is None:
                continue
            for frame in (removed_item.get("provenance_json") or {}).get("frames") or []:
                if frame.get("image_name") not in seen_images:
                    frames.append(frame)
                    seen_images.add(frame.get("image_name"))
            db.delete_inventory_item(conn, item_id)

        provenance = dict(keeper.get("provenance_json") or {})
        provenance["capture_mode"] = "multi_image_merged"
        provenance["frames"] = frames
        db.update_inventory_item(conn, keeper_id, provenance_json=provenance)

        duplicates_removed.append({"kept_item_id": keeper_id, "removed_item_ids": removed_ids})

    removed_ids_flat = {
        item_id for entry in duplicates_removed for item_id in entry["removed_item_ids"]
    }
    room_labels_assigned: dict[str, str] = {}
    for image_name, label in response.get("room_labels", {}).items():
        capture = by_image.get(image_name)
        if capture is None or not label:
            continue
        for item_id in capture.measured_item_ids:
            if item_id in removed_ids_flat:
                continue
            db.update_inventory_item(conn, item_id, room_label=label)
        room_labels_assigned[image_name] = label

    return {
        "duplicates_removed": duplicates_removed,
        "room_labels_assigned": room_labels_assigned,
    }
