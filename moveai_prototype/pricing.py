"""Pricing engine -- pure functions, no I/O, mirroring pipeline.py/geometry.py
in staying Streamlit-agnostic (IMPLEMENTATION_ROADMAP.md Build 3).

Consumes db.py row dicts directly: `db.list_inventory_items()` rows and a
`db.get_active_pricing_config()` row. Produces a `Quote` whose
`quote_to_db_kwargs()` output drops straight into `db.create_quote()`.

Every numeric constant here that isn't sourced from `pricing_config` is a
placeholder cross-checked against Hong Kong market research (Consumer
Council removal-company survey, Lalamove/GoGoX fleet specs), not measured
data -- see DESIGN.md's Calibration section.

Hard constraint (DESIGN.md SS5c): margin is applied in exactly one place,
`upper_bound_volume_m3()`. No other function in this module may add a
second margin -- truck sizing uses honest usable capacity, not a padded
nominal figure, and the module docstrings say so explicitly.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

# Hong Kong Consumer Council survey (20 removal companies): stair/no-lift
# charges run 15-20% of the total per floor (one floor = 15-20 steps), up
# to 30% at the priciest outlier. Access legs combine additively (not
# multiplicatively) so a hard job at one end doesn't compound against the
# other end -- this matches DESIGN.md SS5c's "never stack margin" principle.
#
# No surveyed HK company itemises a parking-distance surcharge (that's a US
# "long carry beyond 75-100 ft" convention) -- FREE_CARRY_DISTANCE_M keeps
# short walks from inflating the quote via a leftover intake field.
FREE_CARRY_DISTANCE_M = 20.0


@dataclass(frozen=True)
class AccessFactors:
    origin_floor: int
    origin_has_lift: bool
    origin_parking_distance_m: float
    destination_floor: int
    destination_has_lift: bool
    destination_parking_distance_m: float

    @classmethod
    def from_intake(cls, intake: dict) -> "AccessFactors":
        return cls(
            origin_floor=int(intake["origin_floor"]),
            origin_has_lift=bool(intake["origin_has_lift"]),
            origin_parking_distance_m=float(intake["origin_parking_distance_m"]),
            destination_floor=int(intake["destination_floor"]),
            destination_has_lift=bool(intake["destination_has_lift"]),
            destination_parking_distance_m=float(
                intake["destination_parking_distance_m"]
            ),
        )


def _leg_multiplier(
    floor: int,
    has_lift: bool,
    parking_distance_m: float,
    config: dict,
) -> float:
    if has_lift and floor > 0:
        leg = float(config["lift_multiplier"])
    elif floor > 0:
        leg = 1.0 + floor * float(config["floor_multiplier_per_level"])
    else:
        leg = 1.0

    excess_m = max(0.0, parking_distance_m - FREE_CARRY_DISTANCE_M)
    leg *= 1.0 + (excess_m / 10.0) * float(config["parking_multiplier_per_10m"])
    return leg


def upper_bound_volume_m3(raw_volume_m3: float, margin_fraction: float) -> float:
    """The one and only place margin is applied (DESIGN.md SS5c)."""
    return raw_volume_m3 * (1.0 + margin_fraction)


def access_multiplier(access: AccessFactors, config: dict) -> float:
    """Additive-excess access multiplier: each leg's surcharge (multiplier
    minus 1) is summed rather than compounded, then clamped.
    """
    origin_leg = _leg_multiplier(
        access.origin_floor,
        access.origin_has_lift,
        access.origin_parking_distance_m,
        config,
    )
    destination_leg = _leg_multiplier(
        access.destination_floor,
        access.destination_has_lift,
        access.destination_parking_distance_m,
        config,
    )
    total = 1.0 + (origin_leg - 1.0) + (destination_leg - 1.0)
    return max(1.0, min(total, float(config["max_access_multiplier"])))


@dataclass(frozen=True)
class QuoteLine:
    inventory_item_id: int
    measurement_basis: str
    raw_volume_m3: float
    volume_m3: float  # upper-bound volume, margin applied once
    price_component: float


@dataclass(frozen=True)
class Quote:
    lines: list[QuoteLine]
    total_volume_m3: float  # sum of raw volumes, pre-margin
    upper_bound_volume_m3: float  # sum of upper-bound volumes
    volume_margin_fraction: float
    access_multiplier: float
    total_price: float
    recommended_truck: str | None
    distance_km: float = 0.0
    distance_fee: float = 0.0
    escalated_item_ids: list[int] = field(default_factory=list)
    unmeasured_item_ids: list[int] = field(default_factory=list)


def _item_raw_volume_m3(item: dict) -> float | None:
    if item.get("unit_volume_m3") is not None:
        return float(item["unit_volume_m3"]) * float(item.get("quantity", 1))
    dims = (item.get("width_m"), item.get("height_m"), item.get("depth_m"))
    if all(d is not None for d in dims):
        return float(dims[0]) * float(dims[1]) * float(dims[2]) * float(
            item.get("quantity", 1)
        )
    return None


def build_quote(
    items: list[dict],
    intake: dict,
    config: dict,
    *,
    fleet: list["TruckOption"] | None = None,
) -> Quote:
    """Build a priced quote from confirmed inventory rows, intake access
    factors, and the active pricing config -- all as returned by db.py.

    Items with `review_state == 'staff_escalate'` or with no resolvable
    volume are excluded from pricing but recorded on the Quote rather than
    silently dropped (DESIGN.md SS5b: a failed measurement is never a log
    line).
    """
    access = AccessFactors.from_intake(intake)
    access_mult = access_multiplier(access, config)
    margin = float(config["volume_margin_fraction"])
    price_per_m3 = float(config["price_per_m3"])
    boxed_labour = float(config["boxed_goods_labour_multiplier"])

    lines: list[QuoteLine] = []
    escalated_item_ids: list[int] = []
    unmeasured_item_ids: list[int] = []
    largest_dimension_m = 0.0
    total_raw = 0.0
    total_upper = 0.0

    for item in items:
        if item.get("review_state") == "staff_escalate":
            escalated_item_ids.append(item["id"])
            continue

        raw_volume = _item_raw_volume_m3(item)
        if raw_volume is None:
            unmeasured_item_ids.append(item["id"])
            continue

        upper_volume = upper_bound_volume_m3(raw_volume, margin)
        labour = boxed_labour if item.get("is_boxed_goods") else 1.0
        price_component = upper_volume * price_per_m3 * access_mult * labour

        lines.append(
            QuoteLine(
                inventory_item_id=item["id"],
                measurement_basis=item["measurement_basis"],
                raw_volume_m3=raw_volume,
                volume_m3=upper_volume,
                price_component=price_component,
            )
        )
        total_raw += raw_volume
        total_upper += upper_volume

        for dim_key in ("width_m", "height_m", "depth_m"):
            dim = item.get(dim_key)
            if dim is not None:
                largest_dimension_m = max(largest_dimension_m, float(dim))

    distance_km = float(intake.get("distance_km") or 0.0)
    distance_fee = distance_km * float(config.get("price_per_km") or 0.0)

    subtotal = (
        float(config["base_callout_fee"])
        + distance_fee
        + sum(line.price_component for line in lines)
    )
    total_price = max(subtotal, float(config["minimum_charge"]))

    truck = recommend_truck(
        total_upper, largest_dimension_m, fleet=fleet or HK_FLEET
    )

    return Quote(
        lines=lines,
        total_volume_m3=total_raw,
        upper_bound_volume_m3=total_upper,
        volume_margin_fraction=margin,
        access_multiplier=access_mult,
        total_price=total_price,
        recommended_truck=truck.label if truck.fits else _multi_trip_label(truck),
        distance_km=distance_km,
        distance_fee=distance_fee,
        escalated_item_ids=escalated_item_ids,
        unmeasured_item_ids=unmeasured_item_ids,
    )


def quote_to_db_kwargs(quote: Quote, *, pricing_config_id: int) -> dict:
    """Shape a Quote for db.create_quote(job_id, **kwargs)."""
    return {
        "pricing_config_id": pricing_config_id,
        "total_volume_m3": quote.total_volume_m3,
        "upper_bound_volume_m3": quote.upper_bound_volume_m3,
        "volume_margin_fraction": quote.volume_margin_fraction,
        "access_multiplier": quote.access_multiplier,
        "distance_km": quote.distance_km,
        "distance_fee": quote.distance_fee,
        "total_price": quote.total_price,
        "recommended_truck": quote.recommended_truck,
        "lines": [
            {
                "inventory_item_id": line.inventory_item_id,
                "measurement_basis": line.measurement_basis,
                "volume_m3": line.volume_m3,
                "price_component": line.price_component,
            }
            for line in quote.lines
        ],
    }


# --------------------------------------------------------------------------
# Truck recommendation (DESIGN.md SS5c: a separate function from price)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class TruckOption:
    label: str
    nominal_volume_m3: float
    max_item_length_m: float
    # Usable household capacity as a fraction of nominal volume, reflecting
    # loading geometry (irregular furniture doesn't tessellate) -- this is
    # deliberately NOT a padding/margin factor layered on top of pricing's
    # own margin; it is an honest capacity number for a different job
    # (fitting furniture) than pricing's (buying insurance against
    # underestimation). See DESIGN.md SS5c: margin applies in one place only.
    usable_fraction: float = 0.72

    @property
    def usable_volume_m3(self) -> float:
        return self.nominal_volume_m3 * self.usable_fraction

    @property
    def fits(self) -> bool:
        return True


# Hong Kong fleet, cross-checked against Lalamove/GoGoX public specs.
HK_FLEET: list[TruckOption] = [
    TruckOption("Van (~5.7 m3)", nominal_volume_m3=5.7, max_item_length_m=2.8),
    TruckOption("14ft / 3-tonne (~11 m3)", nominal_volume_m3=11.0, max_item_length_m=4.3),
    TruckOption("16ft / 5.5-tonne (~18 m3)", nominal_volume_m3=18.0, max_item_length_m=5.9),
    TruckOption("9-10 tonne (~33 m3)", nominal_volume_m3=33.0, max_item_length_m=8.3),
]


@dataclass(frozen=True)
class TruckRecommendation:
    label: str
    fits: bool
    trips: int
    oversize_item: bool


def _multi_trip_label(rec: "TruckRecommendation") -> str:
    if rec.oversize_item:
        return f"{rec.label} (oversize item -- verify access, may need disassembly)"
    return f"{rec.label} x {rec.trips} trips"


def recommend_truck(
    upper_bound_volume_m3: float,
    largest_item_dimension_m: float,
    *,
    fleet: list[TruckOption] | None = None,
) -> TruckRecommendation:
    """Select the smallest truck whose usable capacity clears the volume and
    whose compartment clears the largest item dimension. Separate from
    pricing per DESIGN.md SS5c: depends on packed volume and the largest
    single dimension, not on price.
    """
    fleet = fleet or HK_FLEET
    candidates = [t for t in fleet if t.max_item_length_m >= largest_item_dimension_m]

    oversize_item = len(candidates) == 0
    if oversize_item:
        # No compartment clears the item; fall back to the largest truck by
        # volume so a trip count can still be estimated, flagged for staff.
        largest = max(fleet, key=lambda t: t.usable_volume_m3)
        trips = max(1, math.ceil(upper_bound_volume_m3 / largest.usable_volume_m3))
        return TruckRecommendation(
            label=largest.label, fits=False, trips=trips, oversize_item=True
        )

    for truck in sorted(candidates, key=lambda t: t.usable_volume_m3):
        if truck.usable_volume_m3 >= upper_bound_volume_m3:
            return TruckRecommendation(
                label=truck.label, fits=True, trips=1, oversize_item=False
            )

    largest_candidate = max(candidates, key=lambda t: t.usable_volume_m3)
    trips = max(1, math.ceil(upper_bound_volume_m3 / largest_candidate.usable_volume_m3))
    return TruckRecommendation(
        label=largest_candidate.label, fits=False, trips=trips, oversize_item=False
    )


# --------------------------------------------------------------------------
# Day-of surcharge (DESIGN.md SS5c: fires on declared quantities being
# wrong, not on measurement error)
# --------------------------------------------------------------------------

# Hong Kong Consumer Council survey: several companies charge +20% of the
# total if actual goods exceed the estimate by >20%, +30-50% if by >50%.
# Tiers are (excess_fraction_threshold, surcharge_fraction_of_total),
# evaluated from the highest threshold down.
DECLARED_EXCESS_TIERS: tuple[tuple[float, float], ...] = (
    (0.50, 0.50),
    (0.20, 0.20),
)


@dataclass(frozen=True)
class SurchargeOutcome:
    excess_fraction: float
    surcharge_fraction: float
    surcharge_amount: float


def declared_excess_surcharge(
    quoted_declared_m3: float,
    actual_declared_m3: float,
    total_price: float,
) -> SurchargeOutcome:
    """Day-of surcharge when a `declared` quantity (boxed goods or a
    manually-entered item) turns out larger than what was declared at quote
    time. Never applies to `measured`/`prior_assisted` volume -- that error
    is the system's, absorbed via the upper-bound margin (DESIGN.md SS5c).
    """
    if quoted_declared_m3 <= 0:
        excess_fraction = 0.0 if actual_declared_m3 <= 0 else float("inf")
    else:
        excess_fraction = max(
            0.0, (actual_declared_m3 - quoted_declared_m3) / quoted_declared_m3
        )

    surcharge_fraction = 0.0
    for threshold, fraction in DECLARED_EXCESS_TIERS:
        if excess_fraction > threshold:
            surcharge_fraction = fraction
            break

    return SurchargeOutcome(
        excess_fraction=excess_fraction,
        surcharge_fraction=surcharge_fraction,
        surcharge_amount=total_price * surcharge_fraction,
    )
