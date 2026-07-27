from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

APP_DIR = Path(__file__).resolve().parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import db
import job_context
from inventory_sync import (
    add_declared_item,
    apply_customer_correction,
    confirm_item,
    review_summary,
    seed_boxed_goods,
    set_boxed_goods_count,
)


st.set_page_config(page_title="MoveAI Inventory Review", page_icon="🧾", layout="wide")
st.title("Inventory Review")
st.caption(
    "Confirm what we measured, adjust the boxed-goods estimate, and add "
    "anything the photos missed. This becomes the inventory your quote is "
    "built from."
)

conn = job_context.get_connection()
job_id = job_context.render_sidebar_job(conn)

if job_id is None:
    st.info("Start an intake and capture a room before reviewing your inventory.")
    try:
        st.page_link("pages/1_Intake.py", label="Start an intake", icon="📝")
    except Exception:
        st.caption("Use the page navigation above to start an intake.")
    st.stop()

intake = db.get_intake(conn, job_id)
pricing_config = db.get_active_pricing_config(conn)

if intake is None:
    st.warning("This job has no intake yet -- access factors won't be available for pricing.")

# Seed the boxed-goods line once (idempotent) so it shows up alongside the
# rest of the review, per DESIGN.md SS4's boxed-goods estimator.
if intake is not None and pricing_config is not None:
    seed_boxed_goods(
        conn,
        job_id,
        room_count=int(intake["room_count"]),
        volume_per_box_m3=float(pricing_config["volume_per_box_m3"]),
    )

items = db.list_inventory_items(conn, job_id)
confirm_items = [
    i for i in items if i["review_state"] == "customer_confirm" and not i["is_boxed_goods"]
]
boxed_goods_item = next((i for i in items if i["is_boxed_goods"]), None)
auto_accept_items = [
    i for i in items if i["review_state"] == "auto_accept" and not i["is_boxed_goods"]
]
escalated_items = [i for i in items if i["review_state"] == "staff_escalate"]

st.divider()
st.header("Needs your confirmation")
if not confirm_items:
    st.caption("Nothing needs your confirmation right now.")
for item in confirm_items:
    with st.container(border=True):
        st.markdown(f"**{item['label']}** — {item.get('room_label') or 'unassigned room'}")
        st.caption(item.get("review_reason") or "Please confirm this item.")
        dims = (item.get("width_m"), item.get("height_m"), item.get("depth_m"))
        if all(d is not None for d in dims):
            st.write(
                f"We measured this at about {dims[0]:.2f} m × {dims[1]:.2f} m × "
                f"{dims[2]:.2f} m (W × H × D). Is that right?"
            )
        col_confirm, col_correct, col_remove = st.columns(3)
        with col_confirm:
            if st.button("✅ Confirm", key=f"confirm_{item['id']}"):
                confirm_item(conn, item["id"])
                st.rerun()
        with col_remove:
            if st.button("🗑️ Remove", key=f"remove_{item['id']}"):
                db.delete_inventory_item(conn, item["id"])
                st.rerun()
        with col_correct:
            with st.popover("✏️ Correct the size"):
                with st.form(f"correct_form_{item['id']}"):
                    st.caption(
                        "Entering your own number means you're supplying this "
                        "measurement -- if it turns out wrong on moving day, "
                        "the day-of surcharge can apply, unlike our own "
                        "estimate."
                    )
                    new_width = st.number_input(
                        "Width (m)", min_value=0.01, value=float(dims[0] or 1.0), step=0.05
                    )
                    new_height = st.number_input(
                        "Height (m)", min_value=0.01, value=float(dims[1] or 1.0), step=0.05
                    )
                    new_depth = st.number_input(
                        "Depth (m)", min_value=0.01, value=float(dims[2] or 1.0), step=0.05
                    )
                    if st.form_submit_button("Save correction"):
                        apply_customer_correction(
                            conn,
                            item["id"],
                            width_m=new_width,
                            height_m=new_height,
                            depth_m=new_depth,
                        )
                        st.rerun()

st.divider()
st.header("Boxed goods")
if boxed_goods_item is None:
    st.caption("No boxed-goods estimate yet -- complete your intake first.")
else:
    seed = boxed_goods_item.get("boxed_goods_seed_json") or {}
    st.write(
        f"We estimated **{int(boxed_goods_item['quantity'])} boxes** "
        f"({boxed_goods_item['unit_volume_m3']:.2f} m³ each) from your rooms "
        "and any detected storage furniture."
    )
    with st.expander("How we got this number"):
        st.json(seed)
    with st.form("boxed_goods_form"):
        new_count = st.number_input(
            "Adjust box count",
            min_value=0,
            step=1,
            value=int(boxed_goods_item["quantity"]),
        )
        if st.form_submit_button("Update box count"):
            set_boxed_goods_count(
                conn,
                boxed_goods_item["id"],
                int(new_count),
                float(boxed_goods_item["unit_volume_m3"]),
            )
            st.rerun()

st.divider()
st.header("Your inventory")
if not auto_accept_items:
    st.caption("No confirmed items yet.")
else:
    rooms: dict[str, list[dict]] = {}
    for item in auto_accept_items:
        rooms.setdefault(item.get("room_label") or "Unassigned", []).append(item)
    for room_label, room_items in rooms.items():
        st.subheader(room_label)
        for item in room_items:
            dims = (item.get("width_m"), item.get("height_m"), item.get("depth_m"))
            dims_text = (
                f"{dims[0]:.2f} × {dims[1]:.2f} × {dims[2]:.2f} m"
                if all(d is not None for d in dims)
                else "declared item"
            )
            col_label, col_remove = st.columns([4, 1])
            with col_label:
                basis_tag = f"`{item['measurement_basis']}`"
                st.write(f"{item['label']} — {dims_text} — {basis_tag}")
            with col_remove:
                if st.button("Remove", key=f"remove_auto_{item['id']}"):
                    db.delete_inventory_item(conn, item["id"])
                    st.rerun()

st.divider()
st.header("Being reviewed by our team")
if not escalated_items:
    st.caption("Nothing is currently escalated.")
else:
    st.caption(
        "These items need a staff look before they can be quoted -- "
        "confirming other items doesn't clear this."
    )
    for item in escalated_items:
        st.warning(f"**{item['label']}** — {item.get('review_reason') or 'Escalated for staff review.'}")

st.divider()
st.header("Add an item we missed")
with st.form("add_declared_item_form"):
    col1, col2 = st.columns(2)
    with col1:
        new_label = st.text_input("Item name")
        new_room = st.text_input("Room")
        new_quantity = st.number_input("Quantity", min_value=1, step=1, value=1)
    with col2:
        add_width = st.number_input("Width (m)", min_value=0.01, value=1.0, step=0.05)
        add_height = st.number_input("Height (m)", min_value=0.01, value=1.0, step=0.05)
        add_depth = st.number_input("Depth (m)", min_value=0.01, value=1.0, step=0.05)
    if st.form_submit_button("Add item"):
        if not new_label.strip():
            st.error("Item name is required.")
        else:
            add_declared_item(
                conn,
                job_id,
                label=new_label.strip(),
                room_label=new_room.strip() or None,
                quantity=new_quantity,
                width_m=add_width,
                height_m=add_height,
                depth_m=add_depth,
            )
            st.rerun()

st.divider()
summary = review_summary(conn, job_id)
st.caption(
    f"{summary['total_items']} item(s) total — "
    f"{summary['auto_accept_count']} ready, "
    f"{summary['customer_confirm_count']} awaiting your confirmation, "
    f"{summary['staff_escalate_count']} with our team."
)
