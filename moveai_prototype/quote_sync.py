"""Bridges pricing.py's pure Quote computation to db.py's versioned quote
storage, and to the Quote page's display needs (IMPLEMENTATION_ROADMAP.md
Build 6). Pure logic, no Streamlit imports -- mirrors how inventory_sync.py
stays Streamlit-agnostic.

Quotes are versioned by insertion, never mutation (DESIGN.md SS5c). Because
a Streamlit page reruns on every widget interaction, a literal "persist a
new version each generation" would spam the version table on every rerun --
`quote_matches()` is the staleness gate that makes persisting idempotent:
the page auto-persists v1 once, then only writes v2+ when a fresh
computation actually differs from the stored active quote.

`staff_review_reasons()` implements the build's resolved product decision:
an item still sitting in `customer_confirm` when the customer reaches the
Quote page costs no money (DESIGN.md SS5c's upper-bound margin already
prices the risk of a measured/prior_assisted item being wrong -- surcharging
it too would charge for that insurance and then decline the claim). Instead
it costs the job an automatic pass-through: the booking needs a staff look
before acceptance. Build 7's Company Console consumes this same function.
"""

from __future__ import annotations

import db
import pricing
from backend import ors_client


_FLOAT_TOL = 1e-6


def _lines_key(lines: list) -> set[tuple]:
    return {
        (
            line.inventory_item_id,
            line.measurement_basis,
            round(line.volume_m3, 6),
            round(line.price_component, 2),
        )
        for line in lines
    }


def _stored_lines_key(stored_lines: list[dict]) -> set[tuple]:
    return {
        (
            line["inventory_item_id"],
            line["measurement_basis"],
            round(line["volume_m3"], 6),
            round(line["price_component"], 2),
        )
        for line in stored_lines
    }


def quote_matches(
    stored_quote: dict, stored_lines: list[dict], fresh: "pricing.Quote"
) -> bool:
    """True if a freshly computed Quote is unchanged from the stored active
    quote -- the staleness gate that keeps rerun-driven Streamlit pages from
    inserting a new quote version on every widget interaction.
    """
    if abs(stored_quote["total_price"] - fresh.total_price) > 0.01:
        return False
    if abs(stored_quote["upper_bound_volume_m3"] - fresh.upper_bound_volume_m3) > _FLOAT_TOL:
        return False
    if abs(stored_quote["volume_margin_fraction"] - fresh.volume_margin_fraction) > _FLOAT_TOL:
        return False
    if abs(stored_quote["access_multiplier"] - fresh.access_multiplier) > _FLOAT_TOL:
        return False
    if abs((stored_quote.get("distance_fee") or 0.0) - fresh.distance_fee) > 0.01:
        return False
    if (stored_quote.get("recommended_truck") or None) != (fresh.recommended_truck or None):
        return False
    return _stored_lines_key(stored_lines) == _lines_key(fresh.lines)


def ensure_intake_distance(conn, job_id: int, intake: dict, config: dict) -> dict:
    """Geocode origin/destination/depot and cache the depot round-trip
    distance on the intake row, if not already cached. ORS availability must
    never block quoting -- any failure leaves `distance_km` unset and the
    caller proceeds with today's behavior (`distance_fee` computes to 0).

    Returns the (possibly updated) intake dict.
    """
    if intake.get("distance_km") is not None:
        return intake

    depot_address = config.get("depot_address")
    if not depot_address:
        return intake

    try:
        depot_lat, depot_lng = config.get("depot_lat"), config.get("depot_lng")
        if depot_lat is None or depot_lng is None:
            depot_coords = ors_client.geocode(depot_address)
            if depot_coords is None:
                return intake
            depot_lat, depot_lng = depot_coords
            db.set_pricing_config_depot_coords(
                conn, config["id"], lat=depot_lat, lng=depot_lng
            )

        origin_lat, origin_lng = intake.get("origin_lat"), intake.get("origin_lng")
        if origin_lat is None or origin_lng is None:
            origin_coords = ors_client.geocode(intake["origin_address"])
            if origin_coords is None:
                return intake
            origin_lat, origin_lng = origin_coords

        destination_lat, destination_lng = (
            intake.get("destination_lat"),
            intake.get("destination_lng"),
        )
        if destination_lat is None or destination_lng is None:
            destination_coords = ors_client.geocode(intake["destination_address"])
            if destination_coords is None:
                return intake
            destination_lat, destination_lng = destination_coords

        distance_km = ors_client.route_distance_km(
            [
                (depot_lat, depot_lng),
                (origin_lat, origin_lng),
                (destination_lat, destination_lng),
                (depot_lat, depot_lng),
            ]
        )
    except ors_client.OrsClientError:
        return intake

    db.set_intake_distance(conn, job_id, distance_km)
    return db.get_intake(conn, job_id)


def persist_quote(
    conn, job_id: int, quote: "pricing.Quote", *, pricing_config_id: int
) -> int:
    """Insert a new quote version and advance the job to 'quoted'."""
    kwargs = pricing.quote_to_db_kwargs(quote, pricing_config_id=pricing_config_id)
    quote_id = db.create_quote(conn, job_id, **kwargs)
    db.set_job_status(conn, job_id, "quoted")
    return quote_id


def staff_review_reasons(items: list[dict], quote: "pricing.Quote") -> list[str]:
    """Plain-language reasons this job can't be auto-approved at booking.

    Derived fresh from rows each visit rather than stored on the quote --
    the inventory itself isn't versioned (roadmap-wide scope exclusion), so
    a stored reason list could go stale the moment the customer edits
    something. Build 7's Company Console calls this too.
    """
    reasons: list[str] = []

    unconfirmed = [
        item
        for item in items
        if item["review_state"] == "customer_confirm"
    ]
    if unconfirmed:
        labels = ", ".join(item["label"] for item in unconfirmed)
        reasons.append(
            f"{len(unconfirmed)} item(s) are still awaiting customer confirmation: {labels}."
        )

    if quote.escalated_item_ids:
        reasons.append(
            f"{len(quote.escalated_item_ids)} item(s) are escalated for staff review "
            "and were not priced."
        )

    if quote.unmeasured_item_ids:
        reasons.append(
            f"{len(quote.unmeasured_item_ids)} item(s) have no resolvable volume "
            "and were not priced."
        )

    truck = quote.recommended_truck or ""
    if "oversize item" in truck:
        reasons.append(
            f"Recommended truck is oversize-flagged: {truck}."
        )
    elif " trips" in truck:
        reasons.append(f"Job requires multiple trips: {truck}.")

    return reasons


def quote_view_rows(items: list[dict], quote: "pricing.Quote") -> list[dict]:
    """Join QuoteLines back to their inventory rows for display."""
    items_by_id = {item["id"]: item for item in items}
    rows = []
    for line in quote.lines:
        item = items_by_id.get(line.inventory_item_id, {})
        rows.append(
            {
                "inventory_item_id": line.inventory_item_id,
                "label": item.get("label", "(unknown item)"),
                "room_label": item.get("room_label"),
                "measurement_basis": line.measurement_basis,
                "raw_volume_m3": line.raw_volume_m3,
                "volume_m3": line.volume_m3,
                "price_component": line.price_component,
                "surcharge_eligible": line.measurement_basis == "declared",
            }
        )
    return rows


def declared_volume_m3(quote: "pricing.Quote") -> float:
    """Total upper-bound volume of declared (surcharge-eligible) lines --
    feeds the day-of surcharge explainer.
    """
    return sum(
        line.volume_m3 for line in quote.lines if line.measurement_basis == "declared"
    )
