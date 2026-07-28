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
from booking_sync import (
    active_booking,
    booking_blockers,
    resubmit_booking,
    submit_booking,
)
from quote_sync import staff_review_reasons


st.set_page_config(page_title="MoveAI Booking", page_icon="📦", layout="wide")
st.title("Booking")
st.caption(
    "Request your booking from your current quote. Our team reviews every "
    "request before it's confirmed."
)

conn = job_context.get_connection()
job_id = job_context.render_sidebar_job(conn)

if job_id is None:
    st.info("Start an intake and get a quote before requesting a booking.")
    try:
        st.page_link("pages/1_Intake.py", label="Start an intake", icon="📝")
    except Exception:
        st.caption("Use the page navigation above to start an intake.")
    st.stop()

intake = db.get_intake(conn, job_id)
config = db.get_active_pricing_config(conn)

if intake is None:
    st.warning("This job has no intake yet -- complete it before booking.")
    try:
        st.page_link("pages/1_Intake.py", label="Complete your intake", icon="📝")
    except Exception:
        st.caption("Use the page navigation above to complete your intake.")
    st.stop()

if config is None:
    st.error("No active pricing configuration -- a booking cannot be requested.")
    st.stop()

items = db.list_inventory_items(conn, job_id)
if not items:
    st.info("No inventory yet -- capture a room and review it before booking.")
    try:
        st.page_link("pages/2_Inventory_Review.py", label="Go to Inventory Review", icon="🧾")
    except Exception:
        st.caption("Use the page navigation above to review your inventory.")
    st.stop()

currency = config["currency"]
booking = active_booking(conn, job_id)

st.divider()

if booking is not None and booking["status"] == "pending_staff_review":
    st.success("Your booking request has been received. Our team is reviewing it.")
    st.write(
        f"Requested price: {currency} {booking['total_price']:,.0f} — "
        f"truck: {booking['recommended_truck'] or 'n/a'}"
    )
    if booking.get("customer_note"):
        st.caption(f"Your note: {booking['customer_note']}")
    fresh_quote = pricing.build_quote(items, intake, config)
    reasons = staff_review_reasons(items, fresh_quote)
    if reasons:
        st.info(
            "Our team will confirm these before your booking is accepted:\n\n"
            + "\n".join(f"- {reason}" for reason in reasons)
        )

elif booking is not None and booking["status"] == "needs_customer_clarification":
    st.warning("Our team has a question before they can confirm your booking.")
    st.write(booking.get("staff_note") or "Please provide more detail.")
    reply = st.text_area("Your reply")
    if st.button("Re-submit for review", type="primary"):
        resubmit_booking(conn, booking["id"], customer_note=reply or None)
        st.rerun()

elif booking is not None and booking["status"] == "confirmed":
    st.success("Your move is booked.")
    st.write(
        f"Confirmed price: {currency} {booking['total_price']:,.0f} — "
        f"truck: {booking['recommended_truck'] or 'n/a'}"
    )
    if booking.get("staff_note"):
        st.caption(f"Note from our team: {booking['staff_note']}")

else:
    stored_quote = db.get_active_quote(conn, job_id)
    stored_lines = db.get_quote_lines(conn, stored_quote["id"]) if stored_quote else []
    fresh_quote = pricing.build_quote(items, intake, config)
    blockers = booking_blockers(stored_quote, stored_lines, fresh_quote)

    if blockers:
        for blocker in blockers:
            st.warning(blocker)
        try:
            st.page_link("pages/3_Quote.py", label="Go to Quote", icon="💰")
        except Exception:
            st.caption("Use the page navigation above to view your quote.")
    else:
        st.header("Confirm your booking")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total price", f"{currency} {stored_quote['total_price']:,.0f}")
        with col2:
            st.metric(
                "Estimated volume (upper bound)",
                f"{stored_quote['upper_bound_volume_m3']:.2f} m³",
            )
        with col3:
            st.metric("Quote version", f"v{stored_quote['version']}")
        st.write(f"**Recommended truck:** {stored_quote['recommended_truck'] or 'n/a'}")
        st.write(f"**From:** {intake['origin_address']}")
        st.write(f"**To:** {intake['destination_address']}")
        if intake.get("preferred_move_date"):
            st.write(f"**Preferred move date:** {intake['preferred_move_date']}")

        reasons = staff_review_reasons(items, fresh_quote)
        if reasons:
            st.info(
                "This job will need a staff look before it's confirmed:\n\n"
                + "\n".join(f"- {reason}" for reason in reasons)
            )

        note = st.text_area("Anything our team should know? (optional)")
        if st.button("Request booking", type="primary"):
            submit_booking(conn, job_id, stored_quote["id"], customer_note=note or None)
            st.rerun()
