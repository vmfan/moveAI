"""Bridges the versioned quote (Build 6) to the booking request queue
(IMPLEMENTATION_ROADMAP.md Build 7). Pure logic, no Streamlit imports --
mirrors how inventory_sync.py and quote_sync.py stay Streamlit-agnostic.

Bookings are not versioned (roadmap-wide scope exclusion): the newest
booking row for a job is the live one. `submit_booking()` guards against a
Streamlit rerun creating a second row the same way Build 6's
`quote_sync.persist_quote()` guards against a duplicate quote version.

`booking_blockers()` is deliberately separate from `quote_sync.
staff_review_reasons()`. The latter never blocks a submission --
DESIGN.md SS5c's "an unconfirmed flag costs a staff review, not money"
extends to booking: a flagged or escalated item still gets to *request* a
booking, it just cannot be auto-approved. `booking_blockers()` only fires on
the two things that make a booking meaningless to submit at all: no quote
exists yet, or the active quote no longer matches the current inventory
(the Quote page only auto-persists the first version and otherwise requires
an explicit Regenerate click -- pages/3_Quote.py -- and a customer can reach
Booking without revisiting Quote at all).
"""

from __future__ import annotations

import db
import pricing
import quote_sync


STAFF_JOB_STATUS = {
    "confirmed": "booked",
    "cancelled": "cancelled",
}


def active_booking(conn, job_id: int) -> dict | None:
    """The newest booking row for this job, or None if never requested."""
    rows = db.list_bookings(conn, job_id=job_id)
    return rows[0] if rows else None


def booking_blockers(
    stored_quote: dict | None, stored_lines: list[dict], fresh_quote: "pricing.Quote"
) -> list[str]:
    """Hard reasons a booking cannot be submitted right now.

    Empty means the customer can request a booking -- it does NOT mean the
    job is auto-approvable; see `quote_sync.staff_review_reasons()` for that
    separate, non-blocking notice.
    """
    if stored_quote is None:
        return ["No quote has been generated yet."]
    if not quote_sync.quote_matches(stored_quote, stored_lines, fresh_quote):
        return [
            "Your inventory has changed since your last quote "
            f"(version {stored_quote['version']}). Regenerate your quote before booking."
        ]
    return []


def submit_booking(
    conn, job_id: int, quote_id: int, *, customer_note: str | None = None
) -> tuple[int, bool]:
    """Create a booking request, or return the existing live one.

    Returns (booking_id, created). A new row is only inserted when there is
    no booking yet or the latest one was cancelled -- a `pending_staff_review`
    or `confirmed` booking is returned unchanged so a Streamlit rerun can't
    duplicate the request.
    """
    existing = active_booking(conn, job_id)
    if existing is not None and existing["status"] != "cancelled":
        return int(existing["id"]), False
    booking_id = db.create_booking(conn, job_id, quote_id, customer_note=customer_note)
    return booking_id, True


def resubmit_booking(conn, booking_id: int, *, customer_note: str | None = None) -> None:
    """Customer reply to a staff clarification request -- flips the booking
    back to pending_staff_review, attaching the reply and preserving the
    staff note.
    """
    booking = db.get_booking(conn, booking_id)
    if booking is None or booking["status"] != "needs_customer_clarification":
        raise ValueError(
            "Can only re-submit a booking that is awaiting customer clarification."
        )
    db.update_booking_status(
        conn, booking_id, "pending_staff_review", customer_note=customer_note
    )


def apply_staff_decision(
    conn, booking_id: int, status: str, *, staff_note: str | None = None
) -> None:
    """Staff status transition -- the single place a booking status maps
    onto job.status. `job.status` becomes 'booked' only on staff
    confirmation, and 'cancelled' only on staff cancellation; a
    clarification request or a return to pending review leaves the job's
    status untouched.
    """
    booking = db.get_booking(conn, booking_id)
    if booking is None:
        raise ValueError(f"No booking with id {booking_id!r}")
    db.update_booking_status(conn, booking_id, status, staff_note=staff_note)
    job_status = STAFF_JOB_STATUS.get(status)
    if job_status is not None:
        db.set_job_status(conn, booking["job_id"], job_status)


def console_rows(conn, *, status: str | None = None) -> list[dict]:
    """Assembles the staff queue: each booking joined with contact/address
    details, the pinned quote, and freshly recomputed review reasons.

    Reasons are recomputed from live rows rather than stored, mirroring
    `quote_sync.staff_review_reasons()`'s own rationale: inventory isn't
    versioned, so a stored reason list goes stale the moment the customer
    edits something.
    """
    rows = []
    for booking in db.list_bookings(conn, status=status):
        job_id = booking["job_id"]
        intake = db.get_intake(conn, job_id)
        items = db.list_inventory_items(conn, job_id)
        config = db.get_active_pricing_config(conn)

        reasons: list[str] = []
        if intake is not None and config is not None and items:
            fresh_quote = pricing.build_quote(items, intake, config)
            reasons = quote_sync.staff_review_reasons(items, fresh_quote)

        active_quote = db.get_active_quote(conn, job_id)
        pinned_quote_superseded = (
            active_quote is not None and active_quote["id"] != booking["quote_id"]
        )

        rows.append(
            {
                "booking": booking,
                "intake": intake,
                "reasons": reasons,
                "pinned_quote_superseded": pinned_quote_superseded,
            }
        )
    return rows
