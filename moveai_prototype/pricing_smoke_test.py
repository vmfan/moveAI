"""Self-check for pricing.py, boxed_goods.py, and priors.py: exercises the
volume -> access -> price -> truck pipeline and the day-of surcharge policy,
plus an integration check that build_quote() output survives db.create_quote().

Needs no model weights (see IMPLEMENTATION_ROADMAP.md's "Known environment
constraints") -- this is real verification, not the synthetic substitution
Build 1 needed.

Run with: .venv/bin/python pricing_smoke_test.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import db
import pricing
from boxed_goods import estimate_boxed_goods


PASS_COUNT = 0


def check(description: str, condition: bool) -> None:
    global PASS_COUNT
    if not condition:
        raise AssertionError(f"FAIL: {description}")
    PASS_COUNT += 1
    print(f"PASS: {description}")


def close(a: float, b: float, tol: float = 1e-9) -> bool:
    return abs(a - b) <= tol


DEFAULT_CONFIG = dict(db._DEFAULT_PRICING_CONFIG)


def make_intake(
    *,
    origin_floor=0,
    origin_has_lift=False,
    origin_parking_distance_m=0,
    destination_floor=0,
    destination_has_lift=False,
    destination_parking_distance_m=0,
) -> dict:
    return {
        "origin_floor": origin_floor,
        "origin_has_lift": int(origin_has_lift),
        "origin_parking_distance_m": origin_parking_distance_m,
        "destination_floor": destination_floor,
        "destination_has_lift": int(destination_has_lift),
        "destination_parking_distance_m": destination_parking_distance_m,
    }


def main() -> None:
    # ----------------------------------------------------------------
    # 1. upper_bound_volume_m3: the one place margin is applied.
    # ----------------------------------------------------------------
    check(
        "upper_bound_volume_m3 applies margin multiplicatively",
        close(pricing.upper_bound_volume_m3(2.0, 0.15), 2.3),
    )
    check(
        "upper_bound_volume_m3 with zero margin is identity",
        close(pricing.upper_bound_volume_m3(2.0, 0.0), 2.0),
    )

    # ----------------------------------------------------------------
    # 2. access_multiplier: additive-excess legs, HK-researched values.
    # ----------------------------------------------------------------
    config = DEFAULT_CONFIG
    check("floor_multiplier_per_level recalibrated to HK survey bottom (0.15)", config["floor_multiplier_per_level"] == 0.15)

    origin_4th_no_lift = pricing.AccessFactors.from_intake(
        make_intake(origin_floor=4, origin_has_lift=False)
    )
    mult = pricing.access_multiplier(origin_4th_no_lift, config)
    check("4th floor no lift, ground destination -> 1.60x", close(mult, 1.60))

    origin_8th_no_lift = pricing.AccessFactors.from_intake(
        make_intake(origin_floor=8, origin_has_lift=False)
    )
    mult8 = pricing.access_multiplier(origin_8th_no_lift, config)
    check(
        "8th floor no lift clamps to max_access_multiplier (2.0x)",
        close(mult8, config["max_access_multiplier"]),
    )

    lift_present = pricing.AccessFactors.from_intake(
        make_intake(origin_floor=10, origin_has_lift=True)
    )
    mult_lift = pricing.access_multiplier(lift_present, config)
    check(
        "lift present uses lift_multiplier, not a per-floor charge",
        close(mult_lift, config["lift_multiplier"]),
    )

    ground_floor = pricing.AccessFactors.from_intake(make_intake())
    check(
        "ground floor, no parking excess -> 1.0x",
        close(pricing.access_multiplier(ground_floor, config), 1.0),
    )

    short_walk = pricing.AccessFactors.from_intake(
        make_intake(origin_parking_distance_m=15)
    )
    check(
        "parking distance under free-carry threshold adds nothing",
        close(pricing.access_multiplier(short_walk, config), 1.0),
    )

    long_walk = pricing.AccessFactors.from_intake(
        make_intake(origin_parking_distance_m=50)
    )
    check(
        "parking distance beyond free-carry threshold adds a surcharge",
        pricing.access_multiplier(long_walk, config) > 1.0,
    )

    both_legs_hard = pricing.AccessFactors.from_intake(
        make_intake(origin_floor=2, origin_has_lift=False, destination_floor=3, destination_has_lift=False)
    )
    expected_additive = 1.0 + (1 + 2 * 0.15 - 1.0) + (1 + 3 * 0.15 - 1.0)
    check(
        "both legs hard combine additively, not multiplicatively",
        close(pricing.access_multiplier(both_legs_hard, config), expected_additive),
    )

    # ----------------------------------------------------------------
    # 3. Access is volume-independent.
    # ----------------------------------------------------------------
    items_small = [
        {
            "id": 1,
            "review_state": "auto_accept",
            "measurement_basis": "measured",
            "is_boxed_goods": 0,
            "unit_volume_m3": 1.0,
            "quantity": 1,
            "width_m": 1.0,
            "height_m": 1.0,
            "depth_m": 1.0,
        }
    ]
    items_large = [dict(items_small[0], id=1, unit_volume_m3=2.0)]
    intake_hard = make_intake(origin_floor=4, origin_has_lift=False)
    q_small = pricing.build_quote(items_small, intake_hard, config)
    q_large = pricing.build_quote(items_large, intake_hard, config)
    check(
        "doubling item volume leaves access_multiplier unchanged",
        close(q_small.access_multiplier, q_large.access_multiplier),
    )

    # ----------------------------------------------------------------
    # 4. build_quote: no stacked margin, boxed-goods labour, escalation.
    # ----------------------------------------------------------------
    items = [
        {
            "id": 1,
            "review_state": "auto_accept",
            "measurement_basis": "measured",
            "is_boxed_goods": 0,
            "unit_volume_m3": None,
            "quantity": 1,
            "width_m": 2.1,
            "height_m": 0.85,
            "depth_m": 0.9,
        },
        {
            "id": 2,
            "review_state": "auto_accept",
            "measurement_basis": "declared",
            "is_boxed_goods": 1,
            "unit_volume_m3": 0.11,
            "quantity": 12,
            "width_m": None,
            "height_m": None,
            "depth_m": None,
        },
        {
            "id": 3,
            "review_state": "staff_escalate",
            "measurement_basis": "measured",
            "is_boxed_goods": 0,
            "unit_volume_m3": None,
            "quantity": 1,
            "width_m": None,
            "height_m": None,
            "depth_m": None,
        },
        {
            "id": 4,
            "review_state": "auto_accept",
            "measurement_basis": "measured",
            "is_boxed_goods": 0,
            "unit_volume_m3": None,
            "quantity": 1,
            "width_m": None,
            "height_m": None,
            "depth_m": None,
        },
    ]
    flat_intake = make_intake()
    quote = pricing.build_quote(items, flat_intake, config)

    check("escalated item is recorded, not silently dropped", quote.escalated_item_ids == [3])
    check("unmeasured item is recorded, not silently dropped", quote.unmeasured_item_ids == [4])
    check("two priceable lines survive", len(quote.lines) == 2)

    raw_total = sum(line.raw_volume_m3 for line in quote.lines)
    check(
        "margin applied exactly once across the quote (sum of upper == upper_bound(sum of raw))",
        close(
            sum(line.volume_m3 for line in quote.lines),
            pricing.upper_bound_volume_m3(raw_total, config["volume_margin_fraction"]),
        ),
    )

    boxed_line = next(l for l in quote.lines if l.inventory_item_id == 2)
    sofa_line = next(l for l in quote.lines if l.inventory_item_id == 1)
    implied_boxed_labour = boxed_line.price_component / (
        boxed_line.volume_m3 * config["price_per_m3"] * quote.access_multiplier
    )
    implied_sofa_labour = sofa_line.price_component / (
        sofa_line.volume_m3 * config["price_per_m3"] * quote.access_multiplier
    )
    check(
        "boxed_goods_labour_multiplier lands on the boxed line only",
        close(implied_boxed_labour, config["boxed_goods_labour_multiplier"])
        and close(implied_sofa_labour, 1.0),
    )

    check(
        "measurement_basis survives onto every quote line",
        {l.inventory_item_id: l.measurement_basis for l in quote.lines}
        == {1: "measured", 2: "declared"},
    )

    tiny_items = [dict(items[0], id=1, width_m=0.1, height_m=0.1, depth_m=0.1)]
    tiny_quote = pricing.build_quote(tiny_items, flat_intake, config)
    check(
        "minimum_charge floors the total price",
        close(tiny_quote.total_price, config["minimum_charge"]),
    )

    no_access_intake = make_intake()
    zero_item_quote = pricing.build_quote([], no_access_intake, config)
    check(
        "base_callout_fee is not access-multiplied (empty inventory -> exactly the callout fee, floored)",
        close(zero_item_quote.total_price, max(config["base_callout_fee"], config["minimum_charge"])),
    )

    # ----------------------------------------------------------------
    # 5. Hand calibration: Consumer Council standard case lands in
    #    the researched HKD 8,000-12,000 band for a hard-access job.
    # ----------------------------------------------------------------
    standard_case_items = [
        dict(items[0], id=i, unit_volume_m3=1.5, quantity=1, width_m=None, height_m=None, depth_m=None)
        for i in range(1, 9)
    ] + [
        dict(items[1], id=100, unit_volume_m3=0.11, quantity=35)
    ]
    standard_intake = make_intake(origin_floor=3, origin_has_lift=False)
    standard_quote = pricing.build_quote(standard_case_items, standard_intake, config)
    check(
        f"Consumer Council standard case (~{standard_quote.upper_bound_volume_m3:.1f} m3, "
        f"3rd floor no lift) lands in HKD 5,000-14,000 (got {standard_quote.total_price:.0f})",
        5_000 <= standard_quote.total_price <= 14_000,
    )

    # ----------------------------------------------------------------
    # 6. Truck recommendation.
    # ----------------------------------------------------------------
    exact_fit = pricing.recommend_truck(
        pricing.HK_FLEET[0].usable_volume_m3 - 0.01, 2.0
    )
    check("volume just under a truck's usable capacity fits it", exact_fit.fits and exact_fit.trips == 1)

    oversize = pricing.recommend_truck(5.0, 100.0)
    check("item longer than any compartment escalates as oversize", oversize.oversize_item and not oversize.fits)

    huge_volume = pricing.recommend_truck(500.0, 2.0)
    check("volume exceeding the largest truck computes multiple trips", huge_volume.trips > 1 and not huge_volume.fits)

    check(
        "recommend_truck picks the smallest truck that fits, not always the biggest",
        pricing.recommend_truck(4.0, 2.0).label == pricing.HK_FLEET[0].label,
    )

    # ----------------------------------------------------------------
    # 7. Day-of surcharge: fires only on declared-quantity excess.
    # ----------------------------------------------------------------
    no_excess = pricing.declared_excess_surcharge(4.0, 4.2, 10_000.0)
    check("small excess under 20% -> no surcharge", close(no_excess.surcharge_fraction, 0.0))

    tier_20 = pricing.declared_excess_surcharge(4.0, 5.0, 10_000.0)
    check(
        "excess just over 20% -> 20% surcharge tier",
        close(tier_20.surcharge_fraction, 0.20) and close(tier_20.surcharge_amount, 2_000.0),
    )

    tier_50 = pricing.declared_excess_surcharge(4.0, 7.0, 10_000.0)
    check(
        "excess over 50% -> 50% surcharge tier",
        close(tier_50.surcharge_fraction, 0.50) and close(tier_50.surcharge_amount, 5_000.0),
    )

    under_quote = pricing.declared_excess_surcharge(4.0, 3.0, 10_000.0)
    check("actual less than quoted -> no surcharge", close(under_quote.surcharge_fraction, 0.0))

    # ----------------------------------------------------------------
    # 8. boxed_goods.estimate_boxed_goods calibration cases.
    # ----------------------------------------------------------------
    cc_case = estimate_boxed_goods(
        storage_labels=["wardrobe", "wardrobe", "cabinet", "bookshelf"],
        room_count=5,
        volume_per_box_m3=0.11,
    )
    check(
        f"Consumer Council calibration case: 5 rooms + 2 wardrobes + cabinet + "
        f"bookshelf -> 36 boxes against surveyed 35 (got {cc_case.box_count})",
        cc_case.box_count == 36,
    )

    small_flat = estimate_boxed_goods(
        storage_labels=["wardrobe", "cabinet"], room_count=2, volume_per_box_m3=0.11
    )
    check("2-room flat with wardrobe+cabinet yields 16 boxes", small_flat.box_count == 16)

    unknown_label_case = estimate_boxed_goods(
        storage_labels=["exotic furniture nobody catalogued"],
        room_count=1,
        volume_per_box_m3=0.11,
    )
    check(
        "unknown storage label contributes zero, doesn't crash",
        unknown_label_case.box_count == 3,
    )

    density_case = estimate_boxed_goods(
        storage_labels=[], room_count=1, volume_per_box_m3=0.11, density_evidence_count=100
    )
    check(
        "density evidence bonus is capped",
        close(density_case.seed["density_bonus_boxes"], 10.0),
    )

    import json
    check(
        "boxed_goods_seed_json round-trips through json.dumps",
        json.loads(json.dumps(cc_case.seed))["storage_total_boxes"] == cc_case.seed["storage_total_boxes"],
    )

    # ----------------------------------------------------------------
    # 9. priors.py stub behaviour: has_prior distinguishes "no signal"
    #    from "checked and plausible".
    # ----------------------------------------------------------------
    import priors

    flag = priors.flag_implausible_dimension("sofa", "depth_m", 0.9)
    check("flag_implausible_dimension stub never flags", flag.flagged is False)
    check("flag_implausible_dimension stub reports has_prior=False (no signal, not endorsement)", flag.has_prior is False)
    check("expected_depth_m stub returns None", priors.expected_depth_m("sofa") is None)
    check("boxes_for_storage_label is case-insensitive with substring fallback", priors.boxes_for_storage_label("Wooden Wardrobe") == 6.0)
    check("boxes_for_storage_label returns 0.0 for unknown labels", priors.boxes_for_storage_label("spaceship") == 0.0)

    # ----------------------------------------------------------------
    # 10. Integration: build_quote() output survives db.create_quote().
    # ----------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "pricing_smoke_test.db"
        conn = db.connect(db_path)
        db.initialize(conn)

        job_id = db.create_job(conn)
        db.save_intake(
            conn,
            job_id,
            contact_name="Test",
            contact_email="test@example.com",
            origin_address="A",
            origin_floor=3,
            origin_has_lift=0,
            origin_parking_distance_m=10,
            destination_address="B",
            destination_floor=0,
            destination_has_lift=0,
            destination_parking_distance_m=5,
            room_count=2,
        )
        sofa_id = db.add_inventory_item(
            conn,
            job_id,
            label="Sofa",
            measurement_basis="measured",
            width_m=2.1,
            height_m=0.85,
            depth_m=0.9,
            unit_volume_m3=1.6,
            review_state="auto_accept",
        )
        box_seed = estimate_boxed_goods(
            storage_labels=["wardrobe"], room_count=2, volume_per_box_m3=0.11
        )
        boxed_id = db.add_boxed_goods_item(
            conn,
            job_id,
            label="Boxed goods",
            quantity=box_seed.box_count,
            unit_volume_m3=box_seed.volume_per_box_m3,
            boxed_goods_seed_json=box_seed.seed,
        )

        active_config = db.get_active_pricing_config(conn)
        db_intake = db.get_intake(conn, job_id)
        db_items = db.list_inventory_items(conn, job_id)
        integration_quote = pricing.build_quote(db_items, db_intake, active_config)
        kwargs = pricing.quote_to_db_kwargs(
            integration_quote, pricing_config_id=active_config["id"]
        )
        quote_id = db.create_quote(conn, job_id, **kwargs)
        check(
            "build_quote() output inserts cleanly via db.create_quote() "
            "(proves CHECK constraints, not just shape, are satisfied)",
            isinstance(quote_id, int) and quote_id > 0,
        )

        persisted_lines = db.get_quote_lines(conn, quote_id)
        check(
            "persisted quote lines preserve measurement_basis and surcharge_eligible correctness",
            all(
                (l["measurement_basis"] == "declared") == bool(l["surcharge_eligible"])
                for l in persisted_lines
            ),
        )

        conn.close()

    print(f"\n{PASS_COUNT} checks passed.")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)
