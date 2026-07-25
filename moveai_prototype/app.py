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

from config import DEFAULT_FURNITURE_CLASSES, PipelineConfig
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

st.markdown(
    """
    <style>
      :root {
        --bg:#08111f;
        --panel:#0f1d33;
        --panel-2:#132642;
        --line:#27466c;
        --text:#e8f1ff;
        --muted:#b3c3dc;
        --accent:#37c6ff;
        --good:#7ff0b0;
        --warn:#ffc46b;
      }
      html, body, [class*="css"] {
        font-family: "Inter", "Segoe UI", Roboto, sans-serif;
      }
      [data-testid="stAppViewContainer"]{
        background: radial-gradient(1800px 900px at 18% -12%, #1d3661 0%, var(--bg) 52%);
      }
      [data-testid="stSidebar"]{
        background: linear-gradient(180deg, #0a172b, #0b1a30);
        border-right: 1px solid #1d3655;
      }
      .block-container {padding-top: 1.5rem; padding-bottom: 2.8rem;}
      .hero {
        padding: 1.55rem 1.75rem;
        border-radius: 20px;
        background: linear-gradient(120deg, #102543, #183560 58%, #1f3f70);
        border: 1px solid #2f5787;
        margin-bottom: 0.95rem;
        box-shadow: 0 16px 36px rgba(0, 0, 0, 0.28);
      }
      .hero h1 {margin: 0; font-size: 2.1rem; letter-spacing: .2px;}
      .hero p {margin: .45rem 0 0; color: var(--muted);}
      .pipeline-strip {
        margin: .55rem 0 1.25rem;
        padding: .7rem .9rem;
        border-radius: 14px;
        border: 1px solid var(--line);
        background: rgba(16, 31, 52, .72);
      }
      .stage {
        display:inline-block; padding:.38rem .62rem; margin:.15rem;
        border-radius:999px; background: #162c4b; border:1px solid #345d88;
        color: #d6e8ff; font-size: .91rem;
      }
      .actual {color:var(--good); font-weight:700;}
      .glass-card {
        background: linear-gradient(180deg, rgba(19,38,66,.92), rgba(14,29,49,.9));
        border:1px solid var(--line);
        border-radius: 14px;
        padding: .95rem 1rem;
      }
      .warning {
        padding:.8rem 1rem; border-left:4px solid var(--warn);
        background:#322618; border-radius:8px; margin-top:.7rem;
      }
      [data-testid="stMetric"] {
        background: linear-gradient(180deg, rgba(20,38,64,.92), rgba(15,29,49,.9));
        border: 1px solid var(--line);
        border-radius: 12px;
        padding: .45rem .55rem;
      }
      [data-testid="stTabs"] [data-baseweb="tab-list"]{
        gap: .35rem; border-bottom: 1px solid #27496f;
      }
      [data-testid="stTabs"] [data-baseweb="tab"]{
        background: #142744;
        border: 1px solid #2e527a;
        border-bottom: none;
        border-radius: 10px 10px 0 0;
        color: #d8e8ff;
        padding: .45rem .8rem;
      }
      [data-testid="stTabs"] [aria-selected="true"]{
        background: #1d3a63 !important;
        color: #fff !important;
      }
      [data-testid="stDataFrame"], [data-testid="stExpander"]{
        border:1px solid var(--line); border-radius:10px;
      }
    </style>
    <div class="hero">
      <h1>MoveAI Volume Lab</h1>
      <p>Language-guided furniture detection and experimental single-image 3D measurement.</p>
    </div>
    <div class="pipeline-strip">
      <span class="stage">Input image + language</span> →
      <span class="stage">Grounding DINO</span> →
      <span class="stage">SAM 2</span> →
      <span class="stage">Depth Pro</span> →
      <span class="stage">Open3D OBB</span>
      <span class="actual"> All stages are live</span>
    </div>
    """,
    unsafe_allow_html=True,
)


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
        length, width, height = item.dimensions_m
        rows.append(
            {
                "#": index,
                "Item": item.label,
                "Detection confidence": round(item.detection_score, 3),
                "OBB edge 1 (m)": round(float(length), 3),
                "OBB edge 2 (m)": round(float(width), 3),
                "OBB edge 3 (m)": round(float(height), 3),
                "Visible OBB (m³)": round(item.visible_obb_volume_m3, 4),
                "Visible OBB (ft³)": round(
                    item.visible_obb_volume_m3 * 35.3147,
                    2,
                ),
                "Median depth (m)": round(item.median_depth_m, 2),
            }
        )
    return rows


st.sidebar.header("Prototype controls")
image, image_name = load_selected_image()
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
    st.subheader("What this prototype proves")
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.markdown(
        """
        - Furniture categories are controlled with **language input**.
        - Detection boxes become precise object masks.
        - Metric depth is estimated without camera metadata.
        - Masked depth pixels become a 3D point cloud.
        - Open3D fits a bounding box around each visible surface.
        """
    )
    st.markdown(
        """
        <div class="warning">
        <strong>Measurement status: experimental.</strong><br>
        A single photograph cannot reveal hidden surfaces. The resulting volume is
        a visible-surface lower bound—not yet a quote-ready transport volume.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

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
        length, width, height = measurement.dimensions_m
        st.caption(
            f"Open3D OBB edges: {length:.2f} × {width:.2f} × "
            f"{height:.2f} m · {measurement.point_count:,} depth points"
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
            for error in result.measurement_errors:
                st.write(error)

with st.expander("Pipeline timing and human-control policy"):
    timing_rows = [
        {"Stage": stage, "Seconds": round(seconds, 2)}
        for stage, seconds in result.timings_s.items()
    ]
    st.dataframe(timing_rows, hide_index=True, width="stretch")
    st.markdown(
        """
        **Human control:** users confirm the generated inventory and moving-company
        staff review low-confidence detections or implausible dimensions. Pricing
        remains outside this prototype and is not simulated here.
        """
    )

