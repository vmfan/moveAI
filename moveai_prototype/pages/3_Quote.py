from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

APP_DIR = Path(__file__).resolve().parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import db
import job_context
import pricing
from inventory_sync import seed_boxed_goods
from quote_sync import (
    declared_volume_m3,
    persist_quote,
    quote_matches,
    quote_view_rows,
    staff_review_reasons,
)


st.set_page_config(page_title="MoveAI Quote", page_icon="💰", layout="wide")
st.title("Quote")
st.caption(
    "A price and truck recommendation built from your confirmed inventory, "
    "access factors, and current pricing."
)

conn = job_context.get_connection()
job_id = job_context.render_sidebar_job(conn)

if job_id is None:
    st.info("Start an intake and review your inventory before viewing a quote.")
    try:
        st.page_link("pages/1_Intake.py", label="Start an intake", icon="📝")
    except Exception:
        st.caption("Use the page navigation above to start an intake.")
    st.stop()

intake = db.get_intake(conn, job_id)
config = db.get_active_pricing_config(conn)

if intake is None:
    st.warning("This job has no intake yet -- access factors are required for a quote.")
    try:
        st.page_link("pages/1_Intake.py", label="Complete your intake", icon="📝")
    except Exception:
        st.caption("Use the page navigation above to complete your intake.")
    st.stop()

if config is None:
    st.error("No active pricing configuration -- a quote cannot be built.")
    st.stop()

# Seed boxed goods here too (idempotent) so a customer who skips straight to
# the quote from capture doesn't get an under-quote missing ~half their
# volume (DESIGN.md SS3). It lands as customer_confirm, which correctly
# trips the unconfirmed-items notice below.
seed_boxed_goods(
    conn,
    job_id,
    room_count=int(intake["room_count"]),
    volume_per_box_m3=float(config["volume_per_box_m3"]),
)

items = db.list_inventory_items(conn, job_id)
if not items:
    st.info("No inventory yet -- capture a room and review it before requesting a quote.")
    try:
        st.page_link("pages/2_Inventory_Review.py", label="Go to Inventory Review", icon="🧾")
    except Exception:
        st.caption("Use the page navigation above to review your inventory.")
    st.stop()

quote = pricing.build_quote(items, intake, config)

stored_quote = db.get_active_quote(conn, job_id)
stored_lines = db.get_quote_lines(conn, stored_quote["id"]) if stored_quote else []

is_stale = stored_quote is not None and not quote_matches(stored_quote, stored_lines, quote)

if stored_quote is None:
    quote_id = persist_quote(conn, job_id, quote, pricing_config_id=config["id"])
    st.success("Quote generated (version 1).")
    stored_quote = db.get_active_quote(conn, job_id)
elif is_stale:
    st.warning(
        "Your inventory has changed since your last quote "
        f"(version {stored_quote['version']})."
    )
    if st.button("Regenerate quote", type="primary"):
        persist_quote(conn, job_id, quote, pricing_config_id=config["id"])
        st.rerun()
else:
    st.caption(f"Showing quote version {stored_quote['version']}.")

currency = config["currency"]

st.divider()
st.header("Estimate")
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total price", f"{currency} {quote.total_price:,.0f}")
with col2:
    st.metric(
        "Estimated volume (upper bound)",
        f"{quote.upper_bound_volume_m3:.2f} m³",
        help=(
            f"Raw estimate {quote.total_volume_m3:.2f} m³, plus a "
            f"{quote.volume_margin_fraction:.0%} margin -- the one place "
            "conservatism is added to the price (DESIGN.md §5c)."
        ),
    )
with col3:
    st.metric(
        "Access multiplier",
        f"{quote.access_multiplier:.2f}x",
        help="Combines floor, lift, and parking-distance surcharges from your intake.",
    )

with st.expander("How access factors were applied"):
    for leg_name, floor_key, lift_key, parking_key in (
        ("Origin", "origin_floor", "origin_has_lift", "origin_parking_distance_m"),
        (
            "Destination",
            "destination_floor",
            "destination_has_lift",
            "destination_parking_distance_m",
        ),
    ):
        floor = intake[floor_key]
        has_lift = bool(intake[lift_key])
        parking = intake[parking_key]
        st.write(
            f"**{leg_name}:** floor {floor}, "
            f"{'lift available' if has_lift else 'no lift'}, "
            f"{parking:.0f} m parking distance"
        )

st.subheader("Recommended truck")
st.write(quote.recommended_truck or "No truck could be recommended.")

st.divider()
st.header("Line items")
rows = quote_view_rows(items, quote)
if not rows:
    st.caption("No priced line items yet.")
else:
    basis_note = {
        "measured": "our estimate -- we cover a measurement error",
        "prior_assisted": "our estimate -- we cover a measurement error",
        "declared": "your figure -- day-of surcharge applies if it's wrong",
    }
    for row in rows:
        with st.container(border=True):
            cols = st.columns([3, 2, 2, 2])
            cols[0].write(f"**{row['label']}** — {row.get('room_label') or 'unassigned room'}")
            cols[1].write(f"`{row['measurement_basis']}`")
            cols[2].write(f"{row['volume_m3']:.2f} m³")
            cols[3].write(f"{currency} {row['price_component']:,.0f}")
            st.caption(basis_note.get(row["measurement_basis"], ""))

st.divider()
st.header("Not priced")
escalated = [i for i in items if i["id"] in quote.escalated_item_ids]
unmeasured = [i for i in items if i["id"] in quote.unmeasured_item_ids]
if not escalated and not unmeasured:
    st.caption("Every item in your inventory was priced.")
else:
    for item in escalated:
        st.warning(
            f"**{item['label']}** — {item.get('review_reason') or 'Escalated for staff review.'} "
            "Not included in this price."
        )
    for item in unmeasured:
        st.warning(f"**{item['label']}** — no resolvable volume. Not included in this price.")

reasons = staff_review_reasons(items, quote)
if reasons:
    st.divider()
    st.warning(
        "This job will need a staff look before your booking is accepted:\n\n"
        + "\n".join(f"- {reason}" for reason in reasons)
    )
    try:
        st.page_link("pages/2_Inventory_Review.py", label="Review flagged items", icon="🧾")
    except Exception:
        st.caption("Use the page navigation above to review flagged items.")
    st.caption("You can still continue -- our team will confirm these before booking.")

st.divider()
with st.expander("What if my declared items turn out wrong?"):
    st.caption(
        "The day-of surcharge only applies to declared quantities you "
        "supplied yourself (boxed goods, manual additions, and any "
        "measurement you corrected) -- never to our own measurements."
    )
    declared_m3 = declared_volume_m3(quote)
    if declared_m3 <= 0:
        st.write("You have no declared items yet, so no surcharge could apply.")
    else:
        st.write(f"Your declared volume today: {declared_m3:.2f} m³.")
        for threshold, fraction in pricing.DECLARED_EXCESS_TIERS:
            example_actual = declared_m3 * (1 + threshold + 0.01)
            outcome = pricing.declared_excess_surcharge(
                declared_m3, example_actual, quote.total_price
            )
            st.write(
                f"If actual declared goods exceed this by more than "
                f"{threshold:.0%} (e.g. {example_actual:.2f} m³), a "
                f"{fraction:.0%} surcharge (~{currency} "
                f"{outcome.surcharge_amount:,.0f}) applies."
            )

st.divider()
with st.expander("Quote version history"):
    quotes = db.list_quotes(conn, job_id)
    for q in quotes:
        status = "active" if not q["is_superseded"] else "superseded"
        st.write(
            f"v{q['version']} ({status}) — {currency} {q['total_price']:,.0f} — "
            f"{q['created_at']}"
        )

st.divider()
st.subheader("Ready to move forward?")
try:
    st.page_link("pages/4_Booking.py", label="Request a booking", icon="📦")
except Exception:
    st.caption("Use the page navigation above to request a booking.")
