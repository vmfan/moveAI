from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import streamlit as st

APP_DIR = Path(__file__).resolve().parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import db
import job_context
from inventory_sync import intake_validation_errors


st.set_page_config(page_title="MoveAI Intake", page_icon="📝", layout="wide")
st.title("Intake")
st.caption(
    "Contact details, addresses, and access factors — the information a "
    "quote needs beyond the measured inventory."
)

conn = job_context.get_connection()
job_id = job_context.current_job_id(conn)
existing_intake = db.get_intake(conn, job_id) if job_id else None

if job_id is not None:
    st.info(f"Editing intake for job #{job_id}. Submitting again updates this job.")

if st.button("Start a new job instead"):
    job_context.clear_current_job()
    st.rerun()

with st.form("intake_form"):
    st.subheader("Contact")
    contact_name = st.text_input(
        "Full name", value=(existing_intake or {}).get("contact_name", "")
    )
    contact_email = st.text_input(
        "Email", value=(existing_intake or {}).get("contact_email", "")
    )
    contact_phone = st.text_input(
        "Phone (optional)", value=(existing_intake or {}).get("contact_phone", "") or ""
    )

    st.subheader("Origin")
    col1, col2, col3 = st.columns(3)
    with col1:
        origin_address = st.text_area(
            "Origin address", value=(existing_intake or {}).get("origin_address", "")
        )
    with col2:
        origin_floor = st.number_input(
            "Origin floor",
            min_value=0,
            step=1,
            value=int((existing_intake or {}).get("origin_floor", 0)),
        )
        origin_has_lift = st.checkbox(
            "Lift available at origin",
            value=bool((existing_intake or {}).get("origin_has_lift", False)),
        )
    with col3:
        origin_parking_distance_m = st.number_input(
            "Origin parking distance (m)",
            min_value=0.0,
            step=5.0,
            value=float((existing_intake or {}).get("origin_parking_distance_m", 0.0)),
        )

    st.subheader("Destination")
    col4, col5, col6 = st.columns(3)
    with col4:
        destination_address = st.text_area(
            "Destination address",
            value=(existing_intake or {}).get("destination_address", ""),
        )
    with col5:
        destination_floor = st.number_input(
            "Destination floor",
            min_value=0,
            step=1,
            value=int((existing_intake or {}).get("destination_floor", 0)),
        )
        destination_has_lift = st.checkbox(
            "Lift available at destination",
            value=bool((existing_intake or {}).get("destination_has_lift", False)),
        )
    with col6:
        destination_parking_distance_m = st.number_input(
            "Destination parking distance (m)",
            min_value=0.0,
            step=5.0,
            value=float(
                (existing_intake or {}).get("destination_parking_distance_m", 0.0)
            ),
        )

    st.subheader("Move details")
    col7, col8 = st.columns(2)
    with col7:
        room_count = st.number_input(
            "Number of rooms",
            min_value=1,
            step=1,
            value=int((existing_intake or {}).get("room_count", 1)),
        )
    with col8:
        existing_date = (existing_intake or {}).get("preferred_move_date")
        preferred_move_date = st.date_input(
            "Preferred move date (optional)",
            value=date.fromisoformat(existing_date) if existing_date else None,
        )

    submitted = st.form_submit_button("Save intake", type="primary")

if submitted:
    fields = {
        "contact_name": contact_name,
        "contact_email": contact_email,
        "contact_phone": contact_phone or None,
        "origin_address": origin_address,
        "origin_floor": origin_floor,
        "origin_has_lift": origin_has_lift,
        "origin_parking_distance_m": origin_parking_distance_m,
        "destination_address": destination_address,
        "destination_floor": destination_floor,
        "destination_has_lift": destination_has_lift,
        "destination_parking_distance_m": destination_parking_distance_m,
        "room_count": room_count,
        "preferred_move_date": (
            preferred_move_date.isoformat() if preferred_move_date else None
        ),
    }

    errors = intake_validation_errors(fields)
    if errors:
        for error in errors:
            st.error(error)
    else:
        if job_id is None:
            job_id = db.create_job(conn)
        db.save_intake(conn, job_id, **fields)
        db.set_job_status(conn, job_id, "capture")
        job_context.set_current_job(job_id)
        st.success(f"Intake saved for job #{job_id}.")
        try:
            st.page_link("app.py", label="Continue to capture", icon="📦")
        except Exception:
            st.caption("Use the page navigation above to continue to capture.")
