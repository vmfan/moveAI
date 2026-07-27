from __future__ import annotations

import json
import sys
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st
from PIL import Image

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import db
import job_context
from config import DEFAULT_FURNITURE_CLASSES, PipelineConfig
from inventory_sync import persist_capture
from pipeline import PipelineResult, run_pipeline
from visualization import (
    point_cloud_figure,
    render_depth_map,
    render_detection_overlay,
)


SAMPLE_DIR = APP_DIR.parent / "real_world_samples" / "images"


st.set_page_config(
    page_title="MoveAI Volume Lab",
    page_icon="📦",
    layout="wide",
)

st.title("MoveAI Volume Lab")
st.caption("Language-guided furniture detection and single-image 3D measurement.")


def load_selected_image() -> tuple[Image.Image | None, str]:
    source = st.sidebar.radio("Image source", ["Built-in sample", "Upload image"])
    if source == "Upload image":
        uploaded = st.sidebar.file_uploader(
            "Room photograph",
            type=["jpg", "jpeg", "png", "webp", "heic"],
        )
        if uploaded is None:
            return None, ""
        return Image.open(BytesIO(uploaded.getvalue())), uploaded.name

    sample_paths = sorted(SAMPLE_DIR.glob("*.jpg")) if SAMPLE_DIR.exists() else []
    if not sample_paths:
        return None, ""
    selected = st.sidebar.selectbox(
        "Real-world sample",
        sample_paths,
        format_func=lambda path: path.name,
    )
    return Image.open(selected), selected.name


def result_rows(result: PipelineResult) -> list[dict[str, object]]:
    rows = []
    for index, item in enumerate(result.measurements, start=1):
        rows.append(
            {
                "#": index,
                "Item": item.label,
                "Detection confidence": round(item.detection_score, 3),
                "Width (m)": round(item.width_m, 3),
                "Height (m)": round(item.height_m, 3),
                "Depth (m)": round(item.depth_m, 3),
                "Visible OBB (m³)": round(item.visible_obb_volume_m3, 4),
                "Visible OBB (ft³)": round(
                    item.visible_obb_volume_m3 * 35.3147,
                    2,
                ),
                "Median depth (m)": round(item.median_depth_m, 2),
            }
        )
    return rows


conn = job_context.get_connection()
active_job_id = job_context.render_sidebar_job(conn)

st.sidebar.header("Prototype controls")
image, image_name = load_selected_image()
room_label = st.sidebar.text_input("Room", value="Living room")
prompt_text = st.sidebar.text_area(
    "Furniture language prompt",
    value=", ".join(DEFAULT_FURNITURE_CLASSES),
    help="Grounding DINO searches only for these language-defined categories.",
    height=145,
)
box_threshold = st.sidebar.slider(
    "Detection threshold",
    min_value=0.10,
    max_value=0.70,
    value=0.30,
    step=0.05,
)
max_detections = st.sidebar.slider(
    "Maximum items",
    min_value=1,
    max_value=12,
    value=6,
)
analyze = st.sidebar.button(
    "Run full AI pipeline",
    type="primary",
    width="stretch",
    disabled=image is None,
)

if image is None:
    st.info("Choose a built-in sample or upload a room photograph to begin.")
    st.stop()

left, right = st.columns([1.45, 1])
with left:
    st.subheader("Input photograph")
    st.image(image, caption=image_name, width="stretch")
with right:
    st.subheader("Pipeline")
    st.markdown(
        "Grounding DINO → SAM 2 → Depth Pro → Open3D OBB"
    )
    st.info(
        "Measurement status: experimental. A single photograph cannot reveal "
        "hidden surfaces, so the resulting volume is a visible-surface lower "
        "bound, not a quote-ready transport volume."
    )

if analyze:
    classes = [part.strip() for part in prompt_text.split(",") if part.strip()]
    config = PipelineConfig(
        box_threshold=box_threshold,
        max_detections=max_detections,
    )
    progress_bar = st.progress(0.0, text="Preparing pipeline")

    def update_progress(message: str, value: float) -> None:
        progress_bar.progress(value, text=message)

    try:
        result = run_pipeline(image, classes, config, update_progress)
        st.session_state["pipeline_result"] = result
        st.session_state["pipeline_image_name"] = image_name
        progress_bar.empty()

        if active_job_id is not None:
            summary = persist_capture(
                conn,
                active_job_id,
                measurements=result.measurements,
                failures=result.measurement_errors,
                room_label=room_label or None,
                source_image_name=image_name,
                focal_length_px=result.focal_length_px,
            )
            db.set_job_status(conn, active_job_id, "inventory_review")
            st.success(
                f"Saved {len(summary['measured_item_ids'])} item(s) "
                f"({len(summary['escalated_item_ids'])} escalated) to job "
                f"#{active_job_id}."
            )
    except Exception as exc:
        progress_bar.empty()
        st.error(f"Pipeline failed: {exc}")
        with st.expander("Technical error details"):
            st.exception(exc)

result = (
    st.session_state.get("pipeline_result")
    if st.session_state.get("pipeline_image_name") == image_name
    else None
)
if not isinstance(result, PipelineResult):
    st.stop()

st.divider()
st.header("Live pipeline output")
metric_1, metric_2, metric_3, metric_4 = st.columns(4)
metric_1.metric("Detected items", len(result.detections))
metric_2.metric("Measured objects", len(result.measurements))
metric_3.metric(
    "Visible OBB total",
    f"{result.total_visible_volume_m3:.3f} m³",
)
metric_4.metric("Estimated focal length", f"{result.focal_length_px:.0f} px")

detection_tab, depth_tab, cloud_tab, inventory_tab = st.tabs(
    ["1 · Detect + segment", "2 · Metric depth", "3 · Open3D", "4 · Inventory"]
)

with detection_tab:
    st.image(
        render_detection_overlay(result.image, result.detections),
        caption="Grounding DINO boxes with SAM 2 masks",
        width="stretch",
    )

with depth_tab:
    col_a, col_b = st.columns(2)
    with col_a:
        st.image(result.image, caption="RGB input", width="stretch")
    with col_b:
        st.image(
            render_depth_map(result.depth_m),
            caption="Depth Pro metric depth (near = warm, far = cool)",
            width="stretch",
        )
    finite_depth = result.depth_m[
        pd.notna(result.depth_m)
    ]
    if finite_depth.size:
        st.caption(
            f"Depth range shown: {finite_depth.min():.2f}–"
            f"{finite_depth.max():.2f} m."
        )

with cloud_tab:
    if result.measurements:
        selected_index = st.selectbox(
            "Object to inspect",
            range(len(result.measurements)),
            format_func=lambda index: (
                f"{index + 1}. {result.measurements[index].label}"
            ),
        )
        measurement = result.measurements[selected_index]
        st.plotly_chart(
            point_cloud_figure(measurement),
            width="stretch",
        )
        st.caption(
            f"Width × Height × Depth: {measurement.width_m:.2f} × "
            f"{measurement.height_m:.2f} × {measurement.depth_m:.2f} m · "
            f"{measurement.point_count:,} depth points"
        )
        st.warning(measurement.warning)
    else:
        st.warning("No object had enough valid depth points for an Open3D box.")

with inventory_tab:
    rows = result_rows(result)
    if rows:
        inventory = pd.DataFrame(rows)
        st.dataframe(inventory, hide_index=True, width="stretch")
        st.download_button(
            "Download inventory JSON",
            data=json.dumps(rows, indent=2),
            file_name="moveai_inventory.json",
            mime="application/json",
        )
    if result.measurement_errors:
        with st.expander("Objects requiring human review"):
            for failure in result.measurement_errors:
                st.write(failure.display)

with st.expander("Pipeline timing and human-control policy"):
    timing_rows = [
        {"Stage": stage, "Seconds": round(seconds, 2)}
        for stage, seconds in result.timings_s.items()
    ]
    st.dataframe(timing_rows, hide_index=True, width="stretch")
    st.caption(
        "Users confirm the generated inventory; low-confidence detections or "
        "implausible dimensions should be reviewed manually. Pricing is not "
        "simulated here."
    )

