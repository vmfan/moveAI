from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from backend_client import BackendError, MoveAIBackend
from shared import FURNITURE_CATALOG

st.set_page_config(
    page_title="Move AI",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
        :root {
            --move-primary: #156082;
            --move-primary-dark: #0F506C;
            --move-primary-light: #1B7A9F;
            --move-secondary: #D9F2D0;
            --move-secondary-dark: #A9D49A;
            --move-background: #F8FAFC;
            --move-surface: #FFFFFF;
            --move-text: #1E293B;
            --move-muted: #64748B;
            --move-border: #E4ECEF;
        }

        .stApp {
            background:
                radial-gradient(circle at top left, rgba(21, 96, 130, 0.11), transparent 30%),
                radial-gradient(circle at bottom right, rgba(217, 242, 208, 0.60), transparent 34%),
                var(--move-background);
            color: var(--move-text);
        }

        .block-container {
            max-width: 1180px;
            padding-top: 1.8rem;
            padding-bottom: 3rem;
        }

        .hero {
            padding: 2rem 2.2rem;
            border-radius: 26px;
            background: linear-gradient(135deg, var(--move-primary) 0%, var(--move-primary-light) 100%);
            color: white;
            box-shadow: 0 20px 50px rgba(21, 96, 130, 0.22);
            margin-bottom: 1.4rem;
        }

        .hero-kicker {
            text-transform: uppercase;
            letter-spacing: 0.12em;
            font-size: 0.75rem;
            font-weight: 700;
            opacity: 0.82;
        }

        .hero h1 {
            font-size: 2.9rem;
            margin: 0.35rem 0 0.4rem 0;
            line-height: 1.05;
        }

        .hero p {
            max-width: 720px;
            margin: 0;
            font-size: 1.06rem;
            opacity: 0.92;
        }

        .step-row {
            display: flex;
            gap: 0.65rem;
            margin: 1.2rem 0 1.8rem 0;
            flex-wrap: wrap;
        }

        .step-pill {
            padding: 0.55rem 0.85rem;
            border-radius: 999px;
            font-size: 0.86rem;
            font-weight: 650;
            border: 1px solid var(--move-secondary-dark);
            background: white;
            color: var(--move-primary);
        }

        .step-pill.active {
            color: white;
            background: var(--move-primary);
            border-color: var(--move-primary);
            box-shadow: 0 8px 18px rgba(21, 96, 130, 0.20);
        }

        .section-card {
            background: rgba(255, 255, 255, 0.96);
            border: 1px solid var(--move-border);
            border-radius: 22px;
            padding: 1.4rem 1.45rem;
            box-shadow: 0 14px 40px rgba(21, 96, 130, 0.08);
            margin-bottom: 1rem;
        }

        .info-box {
            background: #F3FAF1;
            border-left: 5px solid var(--move-primary);
            border-radius: 13px;
            padding: 0.85rem 1rem;
            color: var(--move-text);
            margin: 0.5rem 0 1rem 0;
        }

        .success-box {
            background: var(--move-secondary);
            border: 1px solid var(--move-secondary-dark);
            border-radius: 18px;
            padding: 1.2rem;
            color: var(--move-primary);
        }

        .metric-label {
            color: var(--move-muted);
            font-size: 0.82rem;
            margin-bottom: 0.25rem;
        }

        .metric-value {
            font-size: 1.75rem;
            font-weight: 760;
            color: var(--move-primary);
        }

        div[data-testid="stMetricValue"] {
            color: var(--move-primary);
        }

        div[data-testid="stButton"] > button,
        div[data-testid="stFormSubmitButton"] > button {
            border-radius: 12px;
            min-height: 46px;
            font-weight: 700;
            border-color: var(--move-primary);
        }

        div[data-testid="stButton"] > button[kind="primary"],
        div[data-testid="stFormSubmitButton"] > button[kind="primary"] {
            background: var(--move-primary);
            color: white;
        }

        div[data-testid="stButton"] > button[kind="primary"]:hover,
        div[data-testid="stFormSubmitButton"] > button[kind="primary"]:hover {
            background: var(--move-primary-dark);
            border-color: var(--move-primary-dark);
        }

        div[data-testid="stButton"] > button:not([kind="primary"]) {
            color: var(--move-primary);
            background: white;
        }

        div[data-testid="stButton"] > button:not([kind="primary"]):hover {
            color: var(--move-primary-dark);
            border-color: var(--move-primary-dark);
            background: #F3FAF1;
        }

        div[data-baseweb="input"]:focus-within,
        div[data-baseweb="textarea"]:focus-within,
        div[data-baseweb="select"] > div:focus-within {
            border-color: var(--move-primary) !important;
            box-shadow: 0 0 0 1px var(--move-primary) !important;
        }

        div[data-testid="stFileUploaderDropzone"] {
            background: #F8FCF7;
            border-color: var(--move-secondary-dark);
            border-radius: 16px;
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
    """,
    unsafe_allow_html=True,
)


def initialise_state() -> None:
    defaults = {
        "step": 1,
        "customer": {},
        "move": {},
        "uploaded_paths": [],
        "uploaded_names": [],
        "furniture": [],
        "quote": {},
        "request_id": None,
        "job_id": None,
        "backend_inventory": None,
        "backend_quote": None,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def render_steps() -> None:
    labels = [
        "1 · Contact",
        "2 · Upload",
        "3 · Furniture",
        "4 · Review",
        "5 · Quote",
    ]
    pills = []
    for index, label in enumerate(labels, start=1):
        active = " active" if index == st.session_state.step else ""
        pills.append(f'<div class="step-pill{active}">{label}</div>')

    st.markdown(
        f'<div class="step-row">{"".join(pills)}</div>',
        unsafe_allow_html=True,
    )


def render_header() -> None:
    st.markdown(
        """
        <div class="hero">
            <div class="hero-kicker">Smart moving quotation</div>
            <h1>Move AI</h1>
            <p>
                Tell us where you are moving, upload room photos or a video,
                confirm your furniture, and receive an instant preliminary quote.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    render_steps()


def go_to(step: int) -> None:
    st.session_state.step = step
    st.rerun()


def sync_furniture_state(job_id: int) -> None:
    inventory = MoveAIBackend().get_inventory(job_id)
    items = inventory.get("items", []) if isinstance(inventory, dict) else []
    furniture = []
    for item in items:
        w, h, d = (float(item.get(k, 0) or 0) for k in ("width_m", "height_m", "depth_m"))
        furniture.append({
            "item_id": item.get("id"),
            "name": item.get("label", "Item"),
            "room_label": item.get("room_label") or "Unassigned room",
            "quantity": float(item.get("quantity", 1) or 1),
            "width_m": w, "height_m": h, "depth_m": d,
            "volume_m3": float(item.get("unit_volume_m3", w * h * d) or w * h * d),
            "measurement_basis": item.get("measurement_basis", ""),
            "review_state": item.get("review_state", "auto_accept"),
            "review_reason": item.get("review_reason"),
            "customer_confirmed": bool(item.get("customer_confirmed")),
        })
    st.session_state.furniture = furniture
    st.session_state.backend_inventory = inventory


def address_autocomplete_field(label: str, key_prefix: str, default_value: str = "") -> dict:
    """Text input + backend-queried suggestion selectbox for one address.

    Streamlit forms don't rerun on inner-widget change until submit, so this
    lives outside `st.form` and is called before it. Returns
    `{"address": str, "lat": float | None, "lng": float | None}` -- lat/lng
    are only set once the user picks a suggestion; otherwise the typed free
    text is used as-is (identical to pre-autocomplete behavior).
    """
    query_key = f"{key_prefix}_query"
    suggestions_key = f"{key_prefix}_suggestions"
    last_query_key = f"{key_prefix}_last_query"
    coords_key = f"{key_prefix}_coords"

    st.session_state.setdefault(query_key, default_value)
    st.session_state.setdefault(suggestions_key, [])
    st.session_state.setdefault(last_query_key, "")
    st.session_state.setdefault(coords_key, None)

    st.markdown(f"**{label}**")
    query = st.text_input(
        label,
        key=query_key,
        placeholder="Street, city, postal code",
        label_visibility="collapsed",
    )

    query_stripped = query.strip()
    if query_stripped != st.session_state[last_query_key]:
        st.session_state[last_query_key] = query_stripped
        st.session_state[coords_key] = None
        if len(query_stripped) >= 4:
            api = MoveAIBackend()
            st.session_state[suggestions_key] = api.autocomplete_address(query_stripped)
        else:
            st.session_state[suggestions_key] = []

    suggestions = st.session_state[suggestions_key]
    if suggestions:
        keep_typed = "Keep typed address"
        options = [keep_typed] + [s["label"] for s in suggestions]
        choice = st.selectbox(
            f"{label} suggestions",
            options=options,
            key=f"{key_prefix}_suggestion_choice",
            label_visibility="collapsed",
        )
        if choice != keep_typed:
            match = next((s for s in suggestions if s["label"] == choice), None)
            if match:
                st.session_state[coords_key] = {"lat": match["lat"], "lng": match["lng"]}

    coords = st.session_state[coords_key]
    return {
        "address": query_stripped,
        "lat": coords["lat"] if coords else None,
        "lng": coords["lng"] if coords else None,
    }


def contact_page() -> None:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Your contact details")
    st.caption("We use these details to prepare and follow up on your moving request.")

    customer = st.session_state.customer
    move = st.session_state.move

    st.subheader("Pickup and destination")
    pickup_addr_col, destination_addr_col = st.columns(2)
    with pickup_addr_col:
        pickup = address_autocomplete_field(
            "Current address *", "pickup_address", move.get("pickup_address", "")
        )
    with destination_addr_col:
        destination = address_autocomplete_field(
            "Destination address *", "destination_address", move.get("destination_address", "")
        )

    with st.form("contact_form"):
        left, right = st.columns(2)

        with left:
            name = st.text_input(
                "Full name *",
                value=customer.get("name", ""),
                placeholder="Alex Morgan",
            )
            email = st.text_input(
                "Email address *",
                value=customer.get("email", ""),
                placeholder="alex@example.com",
            )
            phone = st.text_input(
                "Phone number *",
                value=customer.get("phone", ""),
                placeholder="+1 555 012 3456",
            )

        with right:
            moving_date = st.date_input("Preferred moving date")
            notes = st.text_area(
                "Additional notes",
                value=move.get("notes", ""),
                placeholder="Parking restrictions, fragile items, preferred time...",
                height=140,
            )

        pickup_col, destination_col = st.columns(2)

        with pickup_col:
            pickup_floor = st.number_input(
                "Pickup floor",
                min_value=0,
                max_value=80,
                value=int(move.get("pickup_floor", 0)),
                step=1,
            )
            pickup_lift = st.toggle(
                "Lift available at pickup",
                value=bool(move.get("pickup_lift", True)),
            )

        with destination_col:
            destination_floor = st.number_input(
                "Destination floor",
                min_value=0,
                max_value=80,
                value=int(move.get("destination_floor", 0)),
                step=1,
            )
            destination_lift = st.toggle(
                "Lift available at destination",
                value=bool(move.get("destination_lift", True)),
            )

        submitted = st.form_submit_button(
            "Continue to upload",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        missing = []
        if not name.strip():
            missing.append("name")
        if not email.strip() or "@" not in email:
            missing.append("valid email")
        if not phone.strip():
            missing.append("phone")
        if not pickup["address"]:
            missing.append("pickup address")
        if not destination["address"]:
            missing.append("destination address")

        if missing:
            st.error("Please provide: " + ", ".join(missing) + ".")
        else:
            st.session_state.customer = {
                "name": name.strip(),
                "email": email.strip(),
                "phone": phone.strip(),
            }
            st.session_state.move = {
                "moving_date": str(moving_date), "notes": notes.strip(),
                "pickup_address": pickup["address"], "pickup_floor": int(pickup_floor),
                "pickup_lift": pickup_lift, "destination_address": destination["address"],
                "destination_floor": int(destination_floor), "destination_lift": destination_lift,
            }
            try:
                with st.spinner("Creating your job..."):
                    api = MoveAIBackend()
                    job_id, _ = api.create_job()
                    api.submit_intake(job_id, {
                        "contact_name": name.strip(), "contact_email": email.strip(),
                        "contact_phone": phone.strip() or None,
                        "origin_address": pickup["address"], "origin_floor": int(pickup_floor),
                        "origin_has_lift": bool(pickup_lift), "origin_parking_distance_m": 0.0,
                        "origin_lat": pickup["lat"], "origin_lng": pickup["lng"],
                        "destination_address": destination["address"], "destination_floor": int(destination_floor),
                        "destination_has_lift": bool(destination_lift), "destination_parking_distance_m": 0.0,
                        "destination_lat": destination["lat"], "destination_lng": destination["lng"],
                        "room_count": 1, "preferred_move_date": str(moving_date),
                    })
                st.session_state.job_id = job_id
                go_to(2)
            except BackendError as exc:
                st.error(str(exc))

    st.markdown("</div>", unsafe_allow_html=True)


def upload_page() -> None:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Upload your rooms")
    st.markdown(
        """
        <div class="info-box">
            Upload one or more room photos, a walkthrough video, or a PDF inventory.
            For this prototype, furniture recognition is simulated.
        </div>
        """,
        unsafe_allow_html=True,
    )

    uploaded_files = st.file_uploader(
        "Choose files from your computer",
        type=["jpg", "jpeg", "png", "webp", "mp4", "mov", "pdf"],
        accept_multiple_files=True,
    )

    image_files = [
        file
        for file in (uploaded_files or [])
        if file.type and file.type.startswith("image/")
    ]

    if uploaded_files:
        st.caption(f"{len(uploaded_files)} file(s) selected")

        if image_files:
            preview_cols = st.columns(min(4, len(image_files)))
            for index, file in enumerate(image_files[:4]):
                with preview_cols[index]:
                    st.image(file, caption=file.name, use_container_width=True)

    back_col, action_col = st.columns([1, 2])

    with back_col:
        if st.button("Back", use_container_width=True):
            go_to(1)

    with action_col:
        if st.button(
            "Get furniture",
            type="primary",
            use_container_width=True,
            disabled=not image_files,
        ):
            try:
                with st.spinner("Uploading photos and detecting furniture..."):
                    api = MoveAIBackend()
                    uploaded = api.upload_images(st.session_state.job_id, image_files)
                    image_names = api.extract_image_names(uploaded)
                    api.capture(st.session_state.job_id, image_names)
                    sync_furniture_state(st.session_state.job_id)
                st.session_state.uploaded_names = image_names
                go_to(3)
            except BackendError as exc:
                st.error(str(exc))

    st.markdown("</div>", unsafe_allow_html=True)


def furniture_page() -> None:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Review and add furniture")
    st.caption(
        "The detected list is editable. Add missing items before requesting the quote."
    )

    with st.spinner("Loading inventory..."):
        sync_furniture_state(st.session_state.job_id)

    furniture = st.session_state.furniture
    job_id = st.session_state.job_id

    staff_escalate = [f for f in furniture if f["review_state"] == "staff_escalate"]
    needs_confirmation = [
        f for f in furniture
        if f["review_state"] == "customer_confirm" and not f["customer_confirmed"]
    ]
    confirmed = [f for f in furniture if f not in staff_escalate and f not in needs_confirmation]

    if needs_confirmation:
        st.markdown("#### Needs your confirmation")
        st.caption("These items were detected with low confidence. Confirm, correct, or remove them.")
        for item in needs_confirmation:
            with st.container():
                cols = st.columns([2.2, 1, 1, 1])
                cols[0].write(f"**{item['name']}** · {item['room_label']}")
                cols[0].caption(
                    f"{item['width_m']:.2f} × {item['height_m']:.2f} × {item['depth_m']:.2f} m"
                    + (f" — {item['review_reason']}" if item.get("review_reason") else "")
                )
                if cols[1].button("Confirm", key=f"confirm_{item['item_id']}", use_container_width=True):
                    try:
                        MoveAIBackend().confirm_item(job_id, item["item_id"])
                        st.rerun()
                    except BackendError as exc:
                        st.error(str(exc))
                correct_toggle = cols[2].toggle("Correct", key=f"toggle_correct_{item['item_id']}")
                if cols[3].button("Remove", key=f"remove_{item['item_id']}", use_container_width=True):
                    try:
                        MoveAIBackend().delete_inventory_item(job_id, item["item_id"])
                        st.rerun()
                    except BackendError as exc:
                        st.error(str(exc))
                if correct_toggle:
                    with st.form(f"correct_form_{item['item_id']}"):
                        cw, ch, cd = st.columns(3)
                        new_w = cw.number_input("Width (m)", min_value=0.01, value=float(item["width_m"] or 0.01), step=0.05)
                        new_h = ch.number_input("Height (m)", min_value=0.01, value=float(item["height_m"] or 0.01), step=0.05)
                        new_d = cd.number_input("Depth (m)", min_value=0.01, value=float(item["depth_m"] or 0.01), step=0.05)
                        if st.form_submit_button("Save correction"):
                            try:
                                MoveAIBackend().correct_item(job_id, item["item_id"], new_w, new_h, new_d)
                                st.rerun()
                            except BackendError as exc:
                                st.error(str(exc))
        st.divider()

    if staff_escalate:
        st.markdown("#### Flagged for staff review")
        for item in staff_escalate:
            st.info(
                f"**{item['name']}** · {item['room_label']} — flagged for staff review, "
                "no action needed from you."
            )
        st.divider()

    if confirmed:
        st.markdown("#### Your inventory")
        rooms: dict[str, list] = {}
        for item in confirmed:
            rooms.setdefault(item["room_label"], []).append(item)
        for room_label, room_items in rooms.items():
            st.markdown(f"**{room_label}**")
            display_df = pd.DataFrame(room_items)[
                ["name", "quantity", "width_m", "height_m", "depth_m", "volume_m3"]
            ].rename(
                columns={
                    "name": "Furniture",
                    "quantity": "Quantity",
                    "width_m": "Width (m)",
                    "height_m": "Height (m)",
                    "depth_m": "Depth (m)",
                    "volume_m3": "Volume / item (m³)",
                }
            )
            st.dataframe(display_df, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("#### Add furniture manually")

    with st.form("add_furniture_form", clear_on_submit=True):
        c1, c2 = st.columns([2, 1])
        with c1:
            item_name = st.selectbox("Furniture item", options=list(FURNITURE_CATALOG.keys()))
            room_label = st.text_input("Room", placeholder="Living room")
        with c2:
            quantity = st.number_input("Quantity", min_value=1, max_value=99, value=1, step=1)
        d1, d2, d3 = st.columns(3)
        with d1: width_m = st.number_input("Width (m)", min_value=0.01, value=1.0, step=0.05)
        with d2: height_m = st.number_input("Height (m)", min_value=0.01, value=1.0, step=0.05)
        with d3: depth_m = st.number_input("Depth (m)", min_value=0.01, value=1.0, step=0.05)
        add_item = st.form_submit_button("Add item", use_container_width=True)

    if add_item:
        try:
            MoveAIBackend().add_declared_item(st.session_state.job_id, {
                "label": item_name, "room_label": room_label.strip() or None,
                "quantity": float(quantity), "width_m": float(width_m),
                "height_m": float(height_m), "depth_m": float(depth_m),
            })
            st.rerun()
        except BackendError as exc:
            st.error(str(exc))

    if confirmed:
        remove_options = [
            f"{index + 1}. {item['name']} ({item['quantity']}×)"
            for index, item in enumerate(confirmed)
        ]
        selected_remove = st.selectbox(
            "Remove an item",
            options=["Select an item"] + remove_options,
        )
        if st.button(
            "Remove selected",
            disabled=selected_remove == "Select an item",
        ):
            remove_index = remove_options.index(selected_remove)
            item_id = confirmed[remove_index].get("item_id")
            try:
                if item_id is not None:
                    MoveAIBackend().delete_inventory_item(st.session_state.job_id, item_id)
                st.rerun()
            except BackendError as exc:
                st.error(str(exc))

    if needs_confirmation:
        st.warning("Please confirm, correct, or remove the flagged items above before requesting your quote.")

    st.divider()
    back_col, next_col = st.columns([1, 2])

    with back_col:
        if st.button("Back to upload", use_container_width=True):
            go_to(2)

    with next_col:
        if st.button(
            "Review request",
            type="primary",
            use_container_width=True,
            disabled=not furniture or bool(needs_confirmation),
        ):
            try:
                with st.spinner("Calculating your quote..."):
                    quote_response = MoveAIBackend().get_quote(st.session_state.job_id)
                st.session_state.backend_quote = quote_response
                quote = quote_response.get("quote", {}) if isinstance(quote_response, dict) else {}
                total = float(quote.get("total_price", 0) or 0)
                volume = float(quote.get("upper_bound_volume_m3", quote.get("total_volume_m3", 0)) or 0)
                st.session_state.quote = {
                    "total_volume_m3": round(volume, 2),
                    "estimated_total": round(total, 2),
                }
                go_to(4)
            except BackendError as exc:
                st.error(str(exc))

    st.markdown("</div>", unsafe_allow_html=True)


def review_page() -> None:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Review your moving request")

    customer = st.session_state.customer
    move = st.session_state.move
    quote = st.session_state.quote

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### Customer")
        st.write(f"**Name:** {customer.get('name', '—')}")
        st.write(f"**Email:** {customer.get('email', '—')}")
        st.write(f"**Phone:** {customer.get('phone', '—')}")
        st.write(f"**Moving date:** {move.get('moving_date', '—')}")

    with c2:
        st.markdown("#### Route")
        st.write(f"**Pickup:** {move.get('pickup_address', '—')}")
        st.write(
            f"Floor {move.get('pickup_floor', 0)} · "
            f"{'Lift available' if move.get('pickup_lift') else 'No lift'}"
        )
        st.write(f"**Destination:** {move.get('destination_address', '—')}")
        st.write(
            f"Floor {move.get('destination_floor', 0)} · "
            f"{'Lift available' if move.get('destination_lift') else 'No lift'}"
        )

    st.divider()

    summary_cols = st.columns(3)
    summary_cols[0].metric(
        "Furniture entries",
        len(st.session_state.furniture),
    )
    summary_cols[1].metric(
        "Estimated volume",
        f"{quote.get('total_volume_m3', 0):.2f} m³",
    )
    estimated_total = float(quote.get("estimated_total", 0))
    estimate_low = estimated_total * 0.90
    estimate_high = estimated_total * 1.10

    summary_cols[2].metric(
        "Estimated price range",
        f"${estimate_low:,.2f} – ${estimate_high:,.2f}",
    )

    st.info(
        "This is an automated estimate with a ±10% range. "
        "A company employee will check the inventory and moving details. "
        "You will receive the confirmed quotation by email."
    )

    try:
        booking_status = MoveAIBackend().get_booking(st.session_state.job_id)
        blockers = booking_status.get("blockers", []) if isinstance(booking_status, dict) else []
    except BackendError:
        blockers = []

    if blockers:
        st.warning(
            "Before you can submit, please resolve:\n"
            + "\n".join(f"- {reason}" for reason in blockers)
        )

    back_col, submit_col = st.columns([1, 2])
    with back_col:
        if st.button("Back to furniture", use_container_width=True):
            go_to(3)

    with submit_col:
        if st.button(
            "Submit to get quote",
            type="primary",
            use_container_width=True,
            disabled=bool(blockers),
        ):
            try:
                with st.spinner("Submitting your request..."):
                    response = MoveAIBackend().submit_booking(st.session_state.job_id, move.get("notes"))
                booking = response.get("booking", {}) if isinstance(response, dict) else {}
                booking_id = booking.get("id") if isinstance(booking, dict) else None
                st.session_state.request_id = f"BOOKING-{booking_id}" if booking_id is not None else f"JOB-{st.session_state.job_id}"
                go_to(5)
            except BackendError as exc:
                if isinstance(exc.detail, list) and exc.detail:
                    st.error("Please resolve:\n" + "\n".join(f"- {reason}" for reason in exc.detail))
                elif isinstance(exc.detail, str) and exc.detail:
                    st.error(exc.detail)
                else:
                    st.error(str(exc))

    st.markdown("</div>", unsafe_allow_html=True)


def quote_page() -> None:
    quote = st.session_state.quote
    request_id = st.session_state.request_id

    estimated_total = float(quote.get("estimated_total", 0))
    estimate_low = estimated_total * 0.90
    estimate_high = estimated_total * 1.10

    st.markdown(
        f"""
        <div class="success-box">
            <h3 style="margin-top:0;">Request submitted successfully</h3>
            <p style="margin-bottom:0;">
                Reference <strong>{request_id}</strong>. A company employee will
                review your inventory and moving details. You will receive the
                confirmed quotation by email.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.write("")
    metric_cols = st.columns(2)
    metric_cols[0].metric(
        "Total estimated volume",
        f"{quote.get('total_volume_m3', 0):.2f} m³",
    )
    metric_cols[1].metric(
        "Estimated price range",
        f"${estimate_low:,.2f} – ${estimate_high:,.2f}",
    )

    st.caption(
        f"Automated midpoint estimate: ${estimated_total:,.2f}. "
        "The displayed range is ±10% and is not yet a confirmed quotation."
    )

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Furniture summary")

    table_rows = []
    for item in st.session_state.furniture:
        table_rows.append(
            {
                "Furniture": item["name"],
                "Quantity": int(item["quantity"]),
                "Volume / item (m³)": round(float(item["volume_m3"]), 3),
            }
        )

    st.dataframe(
        pd.DataFrame(table_rows),
        use_container_width=True,
        hide_index=True,
    )

    st.info(
        "A company employee will check the detected furniture, quantities, "
        "volume, access conditions, and route. The final confirmed price will "
        "be sent to the email address provided in your request."
    )

    if st.button("Start a new request", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


initialise_state()
render_header()

pages = {
    1: contact_page,
    2: upload_page,
    3: furniture_page,
    4: review_page,
    5: quote_page,
}

pages[st.session_state.step]()
