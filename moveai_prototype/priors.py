"""Class-priors artifact -- DESIGN.md SS4 names this as one artifact serving
three jobs: plausibility bounds, occluded-axis substitution, and box-count
ratios. Only the third is populated this milestone (Build 3); the first two
are explicit no-signal stubs so callers can tell "no prior exists" apart from
"checked and plausible" rather than reading a bare False as an endorsement.

Box-count ratios are rule-of-thumb, cross-checked against a Hong Kong
Consumer Council survey case (5-person flat, 40 furniture items, 35 cartons)
-- see boxed_goods.py's docstring for the worked calibration. Every figure
here is a placeholder per DESIGN.md's Calibration section, not measured data.
"""

from __future__ import annotations

from dataclasses import dataclass


# Expected box-equivalent yield per unit of detected storage furniture.
# Placeholder ratios, not measured data -- see module docstring.
BOXES_PER_STORAGE_ITEM: dict[str, float] = {
    "wardrobe": 6.0,
    "cabinet": 4.0,
    "chest of drawers": 4.0,
    "bookshelf": 5.0,
    "bookcase": 5.0,
    "desk": 2.0,
    "dining table": 1.0,
    "sideboard": 4.0,
    "cupboard": 4.0,
    "dresser": 4.0,
}

# Loose goods baseline per room not held in visible storage furniture
# (clothes, kitchenware, miscellany that never sits inside a wardrobe/cabinet).
BOXES_PER_ROOM_BASELINE = 3.0

# Below-floor "density evidence" objects (DESIGN.md SS5a) are not inventory
# lines but do signal extra clutter -- a cluttered counter implies more boxes
# than an empty one.
BOXES_PER_DENSITY_EVIDENCE_ITEM = 0.5
MAX_BOXES_FROM_DENSITY_EVIDENCE = 10.0


def boxes_for_storage_label(label: str) -> float:
    """Expected box-equivalent yield for one unit of `label`.

    Case-insensitive with substring fallback (e.g. "wooden wardrobe" matches
    "wardrobe"). Unknown labels yield 0.0 -- absence of a prior, not a flag.
    """
    normalized = label.strip().lower()
    if normalized in BOXES_PER_STORAGE_ITEM:
        return BOXES_PER_STORAGE_ITEM[normalized]
    for key, value in BOXES_PER_STORAGE_ITEM.items():
        if key in normalized:
            return value
    return 0.0


@dataclass(frozen=True)
class DimensionFlag:
    """Result of a plausibility check against the class-priors table.

    `has_prior` is the load-bearing field: it lets a caller distinguish "no
    prior exists for this class, no signal available" from "a prior exists
    and this measurement passed it". A bare `flagged=False` cannot make that
    distinction, and DESIGN.md SS5b's interrupt rule depends on it.
    """

    flagged: bool
    has_prior: bool
    reason: str | None = None


def flag_implausible_dimension(
    label: str, axis: str, value_m: float
) -> DimensionFlag:
    """Stub: no class-priors plausibility table is populated this milestone
    (IMPLEMENTATION_ROADMAP.md Build 3 scope). Always reports no signal.
    """
    return DimensionFlag(flagged=False, has_prior=False, reason=None)


def expected_depth_m(label: str) -> float | None:
    """Stub: occluded-axis substitution table is not populated this
    milestone. Always reports no prior available.
    """
    return None
