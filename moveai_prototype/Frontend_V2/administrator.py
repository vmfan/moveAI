from __future__ import annotations

import pandas as pd
import streamlit as st

from backend_client import BackendError, MoveAIBackend

st.set_page_config(page_title="Move AI Administrator", page_icon="🧭", layout="wide")
st.markdown("""
<style>
:root {
    --move-primary: #156082;
    --move-primary-dark: #0F506C;
    --move-primary-light: #1B7A9F;
    --move-secondary: #D9F2D0;
    --move-secondary-dark: #A9D49A;
    --move-background: #F8FAFC;
    --move-text: #1E293B;
    --move-muted: #64748B;
    --move-border: #E4ECEF;
}

.stApp {
    background:
        radial-gradient(circle at top left, rgba(21, 96, 130, 0.10), transparent 30%),
        radial-gradient(circle at bottom right, rgba(217, 242, 208, 0.55), transparent 34%),
        var(--move-background);
    color: var(--move-text);
}

.block-container {
    max-width: 1280px;
    padding-top: 1.6rem;
    padding-bottom: 3rem;
}

.admin-header {
    padding: 1.7rem 1.9rem;
    border-radius: 24px;
    color: white;
    background: linear-gradient(135deg, var(--move-primary) 0%, var(--move-primary-light) 100%);
    box-shadow: 0 18px 42px rgba(21, 96, 130, 0.22);
    margin-bottom: 1.3rem;
}

.admin-header h1 {
    margin: 0;
    font-size: 2.35rem;
}

.admin-header p {
    margin: 0.45rem 0 0;
    opacity: 0.88;
}

.request-card {
    background: rgba(255, 255, 255, 0.97);
    border: 1px solid var(--move-border);
    border-radius: 20px;
    padding: 1.2rem 1.3rem;
    box-shadow: 0 10px 28px rgba(21, 96, 130, 0.07);
    margin-bottom: 1rem;
}

div[data-testid="stMetricValue"] {
    color: var(--move-primary);
}

div[data-testid="stButton"] > button {
    border-radius: 12px;
    min-height: 44px;
    font-weight: 700;
    border-color: var(--move-primary);
}

div[data-testid="stButton"] > button[kind="primary"] {
    background: var(--move-primary);
    color: white;
}

div[data-testid="stButton"] > button[kind="primary"]:hover {
    background: var(--move-primary-dark);
    border-color: var(--move-primary-dark);
}

div[data-testid="stButton"] > button:not([kind="primary"]) {
    color: var(--move-primary);
    background: var(--move-secondary);
    border-color: var(--move-secondary-dark);
}

div[data-testid="stButton"] > button:not([kind="primary"]):hover {
    color: var(--move-primary-dark);
    background: #CBEAC0;
    border-color: var(--move-primary-dark);
}

div[data-baseweb="input"]:focus-within,
div[data-baseweb="textarea"]:focus-within,
div[data-baseweb="select"] > div:focus-within {
    border-color: var(--move-primary) !important;
    box-shadow: 0 0 0 1px var(--move-primary) !important;
}

a {
    color: var(--move-primary);
}

/* Move AI targeted widget colors only */

/* Primary action buttons */
button[data-testid="stBaseButton-primary"],
button[kind="primary"],
div[data-testid="stButton"] button[kind="primary"],
div[data-testid="stFormSubmitButton"] button[kind="primary"] {
    background-color: #156082 !important;
    border-color: #156082 !important;
    color: #FFFFFF !important;
}

button[data-testid="stBaseButton-primary"]:hover,
button[kind="primary"]:hover,
div[data-testid="stButton"] button[kind="primary"]:hover,
div[data-testid="stFormSubmitButton"] button[kind="primary"]:hover {
    background-color: #0F506C !important;
    border-color: #0F506C !important;
    color: #FFFFFF !important;
}

/* Secondary buttons: white background, blue text */
button[data-testid="stBaseButton-secondary"],
button[kind="secondary"],
div[data-testid="stButton"] button:not([kind="primary"]),
div[data-testid="stFormSubmitButton"] button:not([kind="primary"]) {
    background-color: #FFFFFF !important;
    border-color: #156082 !important;
    color: #156082 !important;
}

button[data-testid="stBaseButton-secondary"]:hover,
button[kind="secondary"]:hover,
div[data-testid="stButton"] button:not([kind="primary"]):hover,
div[data-testid="stFormSubmitButton"] button:not([kind="primary"]):hover {
    background-color: #F3F8FA !important;
    border-color: #0F506C !important;
    color: #0F506C !important;
}

/* Toggle element only */
div[data-testid="stToggle"] [role="switch"][aria-checked="true"] {
    background-color: #156082 !important;
    border-color: #156082 !important;
}

div[data-testid="stToggle"] [role="switch"][aria-checked="false"] {
    background-color: #D9DEE3 !important;
    border-color: #C7CED4 !important;
}

/* Keep toggle labels completely untouched */
div[data-testid="stToggle"] label,
div[data-testid="stToggle"] p,
div[data-testid="stToggle"] span {
    background: transparent !important;
    color: inherit !important;
}

/* Keep all text fields white */
div[data-testid="stTextInput"] input,
div[data-testid="stTextArea"] textarea,
div[data-testid="stNumberInput"] input,
div[data-baseweb="select"] > div,
div[data-testid="stDateInput"] input {
    background-color: #FFFFFF !important;
    color: #1E293B !important;
}

/* Blue focus ring only */
div[data-testid="stTextInput"] input:focus,
div[data-testid="stTextArea"] textarea:focus,
div[data-testid="stNumberInput"] input:focus,
div[data-testid="stDateInput"] input:focus {
    border-color: #156082 !important;
    box-shadow: 0 0 0 1px #156082 !important;
}

/* File uploader button only */
div[data-testid="stFileUploader"] button {
    background-color: #FFFFFF !important;
    border-color: #156082 !important;
    color: #156082 !important;
}

div[data-testid="stFileUploader"] button:hover {
    background-color: #F3F8FA !important;
    border-color: #0F506C !important;
    color: #0F506C !important;
}

</style>
""", unsafe_allow_html=True)
st.markdown("""<div class="admin-header"><h1>Move AI Administrator</h1><p>Review backend requests, inventory estimates and approve or decline bookings.</p></div>""", unsafe_allow_html=True)

if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

api = MoveAIBackend()
try:
    raw = api.list_console_jobs()
except BackendError as exc:
    st.error(str(exc))
    st.stop()

jobs = raw if isinstance(raw, list) else []

if not jobs:
    st.info("No requests are available in the backend console.")
    st.stop()

# Each entry is {"booking": {...joined booking row...}, "intake": {...}|None,
# "reasons": [...], "pinned_quote_superseded": bool} per booking_sync.console_rows.

def jid(entry):
    return int(entry.get("booking", {}).get("job_id"))

def status(entry):
    return str(entry.get("booking", {}).get("status", "Unknown"))

def contact_name(entry):
    intake = entry.get("intake") or {}
    return intake.get("contact_name", "Customer")

status_options = ["All"] + sorted({status(job) for job in jobs})
selected_status = st.selectbox("Status", status_options)
filtered = [j for j in jobs if selected_status == "All" or status(j) == selected_status]

m1, m2, m3 = st.columns(3)
m1.metric("All requests", len(jobs))
m2.metric("Pending", sum(status(j).lower() in {"pending_staff_review", "needs_customer_clarification"} for j in jobs))
m3.metric("Approved", sum(status(j).lower() == "confirmed" for j in jobs))

labels = {f"JOB-{jid(j)} · {contact_name(j)} · {status(j)}": j for j in reversed(filtered)}
if not labels:
    st.warning("No requests match this filter.")
    st.stop()
selected = labels[st.selectbox("Select request", list(labels))]
job_id = jid(selected)
selected_booking = selected.get("booking", {})
booking_id = selected_booking.get("id")
intake = selected.get("intake") or {}

try:
    inventory = api.get_inventory(job_id)
except BackendError as exc:
    inventory = {"items": [], "error": str(exc)}
try:
    quote = api.get_quote(job_id)
except BackendError as exc:
    quote = {"error": str(exc)}

customer = intake
move = intake
items = inventory.get("items", []) if isinstance(inventory, dict) else []
if not isinstance(items, list): items = []

st.markdown('<div class="request-card">', unsafe_allow_html=True)
a,b,c = st.columns([1.2,1.7,1])
with a:
    st.subheader(f"JOB-{job_id}")
    st.write(f"**{customer.get('contact_name', 'Customer')}**")
    st.write(customer.get("contact_email", "—"))
    st.write(customer.get("contact_phone", "—"))
with b:
    st.markdown("#### Route")
    st.write(f"**From:** {move.get('origin_address', '—')}")
    st.caption(f"Floor {move.get('origin_floor', 0)} · {'Lift' if move.get('origin_has_lift') else 'No lift'}")
    st.write(f"**To:** {move.get('destination_address', '—')}")
    st.caption(f"Floor {move.get('destination_floor', 0)} · {'Lift' if move.get('destination_has_lift') else 'No lift'}")
with c:
    quote_body = quote.get("quote", {}) if isinstance(quote, dict) else {}
    total = quote_body.get("total_price", selected_booking.get("total_price", 0))
    volume = quote_body.get("upper_bound_volume_m3", quote_body.get("total_volume_m3", 0))
    st.metric("Estimated total", f"${float(total or 0):,.2f}")
    st.write(f"Volume: **{float(volume or 0):.2f} m³**")
st.markdown('</div>', unsafe_allow_html=True)

left,right = st.columns([1,1.6])
with left:
    st.markdown('<div class="request-card">', unsafe_allow_html=True)
    st.subheader("Capture data")
    try:
        image_names = (api.get_capture_images(job_id) or {}).get("image_names", [])
    except BackendError:
        image_names = []
    if image_names:
        for name in image_names:
            try:
                st.image(api.capture_overlay_url(job_id, name), caption=name, use_container_width=True)
            except Exception:
                st.write(f"📎 {name}")
    else:
        st.info(
            "No captured images available. Capture artifacts live in an in-memory "
            "cache and are lost after a backend restart, even though the job's "
            "saved inventory is unaffected."
        )
    st.markdown('</div>', unsafe_allow_html=True)
with right:
    st.markdown('<div class="request-card">', unsafe_allow_html=True)
    st.subheader("Furniture estimation")
    rows=[]
    for item in items:
        q=float(item.get("quantity",1) or 1); w=float(item.get("width_m",0) or 0); h=float(item.get("height_m",0) or 0); d=float(item.get("depth_m",0) or 0)
        v=float(item.get("unit_volume_m3", w*h*d) or 0)
        rows.append({"Furniture":item.get("label","Item"),"Room":item.get("room_label",""),"Qty":q,"Width (m)":w,"Height (m)":h,"Depth (m)":d,"Volume (m³)":v,"Source":item.get("measurement_basis","")})
    if rows: st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
    else: st.info("No inventory items returned by the backend.")
    st.markdown("#### Raw quote")
    st.json(quote)
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="request-card">', unsafe_allow_html=True)
st.subheader("Administrator decision")
note = st.text_area("Staff note", value=str(selected_booking.get("staff_note", "") or ""))
approve, decline = st.columns(2)
with approve:
    if st.button("Approve quote", type="primary", use_container_width=True):
        try:
            api.staff_decision(booking_id, "confirmed", note)
            st.session_state["flash"] = "Request approved in the backend."
            st.rerun()
        except BackendError as exc: st.error(str(exc))
with decline:
    if st.button("Decline request", use_container_width=True):
        try:
            api.staff_decision(booking_id, "cancelled", note)
            st.session_state["flash"] = "Request declined in the backend."
            st.rerun()
        except BackendError as exc: st.error(str(exc))
st.markdown('</div>', unsafe_allow_html=True)
