# MoveAI Prototype

Interactive partial prototype for Presentation 2:

`language + room image → Grounding DINO → SAM 2 → Depth Pro → Open3D OBB`

## What is implemented

- **Grounding DINO:** detects user-specified furniture categories from language.
- **SAM 2.1 Tiny:** converts each detection box into an object mask.
- **Apple Depth Pro:** estimates metric depth and focal length from one RGB image.
- **Open3D:** back-projects masked depth pixels into 3D and fits an oriented bounding box.
- **Streamlit UI:** displays masks, depth, itemized dimensions, downloadable inventory, and interactive point clouds.
- **Human control:** users can change class prompts and thresholds; low-confidence or failed measurements are explicitly surfaced for review.

All four AI/geometry stages are live. Pricing is intentionally excluded rather than simulated.

## UI and showcase design

The frontend has been updated for a presentation-ready look:

- professional dark gradient background with improved contrast;
- consistent typography and spacing for readability on projector screens;
- visual hierarchy with hero header, pipeline strip, metric cards, and polished tabs;
- improved sidebar styling for controls;
- warning and review states clearly highlighted in amber;
- inventory and timing tables framed as report panels.

This keeps the design clean for pitching while preserving technical transparency.

## Run the showcase

From this folder:

```bash
.venv/bin/python -m streamlit run app.py
```

The current development server runs at:

```text
http://127.0.0.1:8505
```

The first complete analysis takes approximately three minutes on the current 8 GB Apple-Silicon Mac. Depth Pro is the dominant stage.

## Demo path

1. Choose a real-world sample or upload a room image.
2. Edit the language prompt to control which furniture categories are searched.
3. Keep the detection threshold around `0.30`.
4. Click **Run full AI pipeline**.
5. Show:
   - Grounding DINO boxes and SAM 2 masks;
   - Depth Pro metric-depth map;
   - Open3D point cloud and bounding box;
   - itemized inventory and exported JSON.
6. Use the timing panel to explain runtime and where optimization is needed.

## Command-line verification

```bash
.venv/bin/python smoke_test.py \
  "../real_world_samples/images/001_3f6e15958d41abf9.jpg" \
  --max-detections 3
```

Verified outputs are stored in `outputs/smoke_test/`.

## Model files

Grounding DINO and SAM 2 are cached through Hugging Face. The official Apple checkpoint is expected at:

```text
checkpoints/depth_pro.pt
```

The checkpoint is approximately 1.9 GB and can be downloaded from:

```text
https://ml-site.cdn-apple.com/models/depth-pro/depth_pro.pt
```

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

