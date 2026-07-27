"""Streamlit glue for the job spine -- shared by app.py and every page.

Keeps session-state/query-param handling in one place so Builds 5-7 don't
each reinvent "how do I find the active job".
"""

from __future__ import annotations

import sqlite3

import streamlit as st

import db


@st.cache_resource
def get_connection() -> sqlite3.Connection:
    conn = db.connect()
    db.initialize(conn)
    return conn


def current_job_id(conn: sqlite3.Connection) -> int | None:
    """Resolve the active job: session_state first, then the `job_id` query
    param (recovers across a browser refresh). A stale/deleted job_id
    resolves to None rather than raising.
    """
    job_id = st.session_state.get("job_id")
    if job_id is None:
        param = st.query_params.get("job_id")
        if param is not None:
            try:
                job_id = int(param)
            except (TypeError, ValueError):
                job_id = None

    if job_id is None:
        return None

    if db.get_job(conn, job_id) is None:
        return None

    st.session_state["job_id"] = job_id
    return job_id


def set_current_job(job_id: int) -> None:
    st.session_state["job_id"] = job_id
    st.query_params["job_id"] = str(job_id)


def clear_current_job() -> None:
    st.session_state.pop("job_id", None)
    if "job_id" in st.query_params:
        del st.query_params["job_id"]


def render_sidebar_job(conn: sqlite3.Connection) -> int | None:
    """Render the active-job status in the sidebar. Returns the job_id, or
    None if the app is running standalone (no intake yet).
    """
    job_id = current_job_id(conn)
    if job_id is None:
        st.sidebar.info("Standalone mode: no active job, nothing is saved.")
        try:
            st.sidebar.page_link("pages/1_Intake.py", label="Start an intake", icon="📝")
        except Exception:
            st.sidebar.caption("Use the page navigation above to start an intake.")
        return None

    intake = db.get_intake(conn, job_id)
    contact_name = intake["contact_name"] if intake else "(intake incomplete)"
    st.sidebar.success(f"Job #{job_id} — {contact_name}")
    if st.sidebar.button("Start a new job"):
        clear_current_job()
        st.rerun()
    return job_id
