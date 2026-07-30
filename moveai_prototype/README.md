# MoveAI Prototype

> **See [`../README.md`](../README.md) first** — it's the canonical entry point for running the full FastAPI + Next.js stack (local, LAN/mobile, and remote testing). This file covers only the legacy standalone Streamlit app below.

`language + room image → Grounding DINO → SAM 2 → Depth Anything V2 → Open3D OBB`

This file covers how to run the prototype. For the architecture, design rationale, and how this fits the wider product, see [`../DESIGN.md`](../DESIGN.md).

## What is implemented

- **Grounding DINO:** detects user-specified furniture categories from language.
- **SAM 2.1 Tiny:** converts each detection box into an object mask.
- **Depth Anything V2 Metric Indoor (Large):** estimates metric depth in meters from one RGB image. Focal length comes from EXIF when available, otherwise an assumed 60° horizontal FOV.
- **Open3D:** back-projects masked depth pixels into 3D and fits an oriented bounding box.
- **Streamlit UI:** displays masks, depth, itemized dimensions, downloadable inventory, and interactive point clouds.
- **Human control:** users can change class prompts and thresholds; low-confidence or failed measurements are explicitly surfaced for review.

All four AI/geometry stages are live. Pricing is implemented as a standalone engine (`pricing.py`, `boxed_goods.py`, `priors.py`; see `../IMPLEMENTATION_ROADMAP.md` Build 3). The app is now six pages: **Intake** (job spine — contact, addresses, access factors), the main **Volume Lab** page, which persists measured items to that job (`../IMPLEMENTATION_ROADMAP.md` Build 4), **Inventory Review** (confirm/correct measured items, adjust the boxed-goods estimate, add missed items — Build 5), **Quote** (priced estimate, truck recommendation, versioned quote history — Build 6), **Booking** (request a booking from the active quote, reply to a staff clarification request — Build 7), and **Company Console** (unauthenticated staff queue: confirm, ask for clarification, or cancel a booking request — Build 7).

## Run the app

From this folder:

```bash
.venv/bin/python -m streamlit run app.py
```

The current development server runs at:

```text
http://127.0.0.1:8505
```

The sidebar page navigation lists **Intake**, the main Volume Lab page, **Inventory Review**, **Quote**, **Booking**, and **Company Console**. Start at Intake to create a job (contact details, origin/destination addresses, floor/lift/parking access factors, room count); the active job persists across pages via `st.session_state` and is mirrored into `st.query_params` so a browser refresh doesn't lose it. Running the pipeline on the Volume Lab page with a job active writes each measured object into `job.db`'s `inventory_item` table (see `db.py`), tagged with the **Room** label from the sidebar; a failed measurement is written as a `staff_escalate` row rather than being dropped, and re-running the same photo replaces its prior rows instead of duplicating them. Inventory Review lets the customer confirm or correct flagged items, adjust the boxed-goods count, and add anything missed. Quote builds a priced estimate from the confirmed inventory, auto-persisting the first version and offering an explicit **Regenerate quote** once the inventory has changed — quotes are versioned by insertion, never mutated. Booking lets the customer request a booking from the active quote (blocked with a link back to Quote if the quote is stale), and shows a staff clarification request with a reply box when one is pending. Company Console is an unauthenticated staff view (prototype only) listing booking requests with Confirm / Ask customer / Cancel actions; confirming a booking is the only thing that advances the job to `booked`. With no active job, the Volume Lab page behaves exactly as before (standalone mode, nothing is saved).

The first complete analysis is dominated by model load + depth inference. Depth Anything V2 is typically faster than the old Depth Pro stage once weights are cached.

Usage: choose a real-world sample or upload a room image, edit the language prompt to control which furniture categories are searched (detection threshold around `0.30` is a reasonable default), then click **Run full AI pipeline**. Results appear in four tabs (detect + segment, metric depth, Open3D, inventory), with an itemized inventory downloadable as JSON and a timing breakdown in the bottom expander.

## Command-line verification

```bash
.venv/bin/python smoke_test.py \
  "../real_world_samples/images/001_3f6e15958d41abf9.jpg" \
  --max-detections 3
```

Verified outputs are stored in `outputs/smoke_test/`.

Persistence-layer checks (no model weights needed):

```bash
.venv/bin/python db_smoke_test.py
.venv/bin/python pricing_smoke_test.py
.venv/bin/python job_flow_smoke_test.py
.venv/bin/python inventory_review_smoke_test.py
.venv/bin/python quote_smoke_test.py
.venv/bin/python booking_smoke_test.py
```

## Model files

Grounding DINO, SAM 2, and Depth Anything V2 Metric Indoor load from Hugging Face:

- `IDEA-Research/grounding-dino-tiny`
- `facebook/sam2.1-hiera-tiny`
- `depth-anything/Depth-Anything-V2-Metric-Indoor-Large-hf`

No Apple Depth Pro checkpoint is required. On low-memory machines you can switch `DEPTH_ANYTHING_V2_MODEL` in `config.py` to the Base or Small indoor metric variant.
## Technical limitation

The fitted Open3D box contains only points visible from one camera view. Hidden backs, undersides, and occluded surfaces are not reconstructed, so its volume is a **single-view visible-surface lower bound**, not a quote-ready transport volume.

Production options include:

- requesting multiple guided views or video;
- using LiDAR/ARKit where available;
- combining measured width/height with class-specific depth priors;
- requiring user confirmation and staff review for implausible dimensions.

## Tested environment

- macOS Apple Silicon
- native Python 3.12
- PyTorch with MPS acceleration
- 8 GB unified memory

