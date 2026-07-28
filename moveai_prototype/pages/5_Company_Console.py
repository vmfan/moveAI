from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

APP_DIR = Path(__file__).resolve().parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import db
import job_context
from booking_sync import apply_staff_decision, console_rows


st.set_page_config(page_title="MoveAI Company Console", page_icon="🏢", layout="wide")
st.title("Company Console")
st.warning(
    "Prototype only -- this page is unauthenticated. Anyone who reaches the "
    "app can read and change every booking here. Not production-ready."
)

conn = job_context.get_connection()

status_options = ("pending_staff_review", "confirmed", "needs_customer_clarification", "cancelled", "all")
status_filter = st.selectbox("Show", status_options, index=0)
status = None if status_filter == "all" else status_filter

rows = console_rows(conn, status=status)

if not rows:
    st.caption("No bookings match this filter.")

for row in rows:
    booking = row["booking"]
    intake = row["intake"]
    reasons = row["reasons"]

    with st.container(border=True):
        st.subheader(
            f"Booking #{booking['id']} — Job #{booking['job_id']} — `{booking['status']}`"
        )
        contact_name = intake["contact_name"] if intake else "(no intake)"
        st.write(f"**Contact:** {contact_name}")
        if intake is not None:
            st.write(f"**From:** {intake['origin_address']}")
            st.write(f"**To:** {intake['destination_address']}")
            if intake.get("preferred_move_date"):
                st.write(f"**Preferred date:** {intake['preferred_move_date']}")
        st.write(
            f"**Price:** {booking['total_price']:,.0f} — "
            f"**Truck:** {booking['recommended_truck'] or 'n/a'} — "
            f"**Job status:** `{booking['job_status']}`"
        )
        if row["pinned_quote_superseded"]:
            st.warning("This booking's pinned quote has been superseded by a newer version.")
        if booking.get("customer_note"):
            st.caption(f"Customer note: {booking['customer_note']}")
        if booking.get("staff_note"):
            st.caption(f"Staff note: {booking['staff_note']}")

        if reasons:
            st.info(
                "Review before approving:\n\n" + "\n".join(f"- {r}" for r in reasons)
            )
        else:
            st.caption("No blockers -- safe to approve.")

        staff_note_input = st.text_input(
            "Staff note", key=f"staff_note_{booking['id']}"
        )

        col_confirm, col_clarify, col_cancel, col_open = st.columns(4)
        with col_confirm:
            if st.button("✅ Confirm", key=f"confirm_{booking['id']}"):
                apply_staff_decision(
                    conn, booking["id"], "confirmed", staff_note=staff_note_input or None
                )
                st.rerun()
        with col_clarify:
            if st.button("❓ Ask customer", key=f"clarify_{booking['id']}"):
                apply_staff_decision(
                    conn,
                    booking["id"],
                    "needs_customer_clarification",
                    staff_note=staff_note_input or None,
                )
                st.rerun()
        with col_cancel:
            if st.button("🗑️ Cancel", key=f"cancel_{booking['id']}"):
                apply_staff_decision(
                    conn, booking["id"], "cancelled", staff_note=staff_note_input or None
                )
                st.rerun()
        with col_open:
            if st.button("🔎 Open this job", key=f"open_{booking['id']}"):
                job_context.set_current_job(booking["job_id"])
                st.rerun()
