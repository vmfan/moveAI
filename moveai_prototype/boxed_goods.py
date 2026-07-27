"""Boxed-goods estimator -- seeds a box-equivalent inventory line from
detected storage furniture and room count, per DESIGN.md SS4/SS5a. The line
this produces is `declared`, not `measured`: no OBB is fit for it, and the
customer adjusts the seeded count during review (Build 5).

Calibrated against a Hong Kong Consumer Council survey case (5-person
family, North Point -> Mei Foo, 40 furniture items + 35 cartons/plastic
boxes): a 5-room flat with 2 wardrobes + 1 cabinet + 1 bookshelf yields
5*3 + (2*6 + 4 + 5) = 15 + 21 = 36 boxes against the surveyed 35. Treat
this as a rule-of-thumb starting point, not measured data (DESIGN.md
Calibration section) -- override with partner job records once available.
"""

from __future__ import annotations

from dataclasses import dataclass

from priors import (
    BOXES_PER_DENSITY_EVIDENCE_ITEM,
    BOXES_PER_ROOM_BASELINE,
    MAX_BOXES_FROM_DENSITY_EVIDENCE,
    boxes_for_storage_label,
)


@dataclass(frozen=True)
class BoxedGoodsEstimate:
    box_count: int
    volume_per_box_m3: float
    total_volume_m3: float
    seed: dict


def estimate_boxed_goods(
    *,
    storage_labels: list[str],
    room_count: int,
    volume_per_box_m3: float,
    density_evidence_count: int = 0,
) -> BoxedGoodsEstimate:
    """Seed a box-equivalent count from detected storage furniture, a
    per-room loose-goods baseline, and optional density evidence
    (DESIGN.md SS5a: below-floor detections that signal extra clutter
    without becoming inventory lines themselves).
    """
    room_baseline = room_count * BOXES_PER_ROOM_BASELINE

    storage_yield: dict[str, float] = {}
    for label in storage_labels:
        yield_boxes = boxes_for_storage_label(label)
        if yield_boxes > 0:
            storage_yield[label] = storage_yield.get(label, 0.0) + yield_boxes
    storage_total = sum(storage_yield.values())

    density_bonus = min(
        density_evidence_count * BOXES_PER_DENSITY_EVIDENCE_ITEM,
        MAX_BOXES_FROM_DENSITY_EVIDENCE,
    )

    raw_count = room_baseline + storage_total + density_bonus
    box_count = round(raw_count)

    seed = {
        "room_count": room_count,
        "room_baseline_boxes": room_baseline,
        "storage_yield": storage_yield,
        "storage_total_boxes": storage_total,
        "density_evidence_count": density_evidence_count,
        "density_bonus_boxes": density_bonus,
        "raw_box_count": raw_count,
    }

    return BoxedGoodsEstimate(
        box_count=box_count,
        volume_per_box_m3=volume_per_box_m3,
        total_volume_m3=box_count * volume_per_box_m3,
        seed=seed,
    )
