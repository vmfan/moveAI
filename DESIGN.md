# MoveAI — Design

## 1. Problem and product shape

Moving companies quote in one of two ways today, and both are bad.

**Photo-and-eyeball.** The customer sends a handful of phone photos; a staff member guesses the volume. Fast, but the estimate carries no measurement behind it. Under-quote and the company absorbs the loss; over-quote and the customer books elsewhere.

**On-site survey.** The company sends someone to measure. Accurate, but it burns a half-day of staff time per lead, forces the customer to take time off, and delays the quote by days — during which the customer is collecting competing bids.

MoveAI is a B2B2C SaaS sold to moving companies that replaces this step: the customer captures their space once, and the system produces a measured inventory and a quote.

### Target user workflow

1. **Intake.** The customer answers structured questions: contact details, origin and destination addresses, floor, lift access, parking distance.
2. **Capture.** The customer uploads a video or photo walkthrough of the space.
3. **Inventory.** After processing, the customer reviews what was found, grouped by room. They confirm whether everything they intend to move is included, and add anything missing — by manual entry, or by photographing it so its volume is estimated too.
4. **Quote.** Once the inventory is confirmed, the system presents a price and truck recommendation, and asks whether to book.
5. **Booking.** Accepted bookings land in the company's request queue, where staff verify the job is safe to proceed or ask the customer for clarification.

### What this repository currently contains

**Only the volume-estimation core of step 3, for a single image.** Given one room photo and a list of furniture category names, it detects those items, segments them, estimates metric depth, and fits a 3D bounding box per object. There is no intake, no video, no room grouping, no persistence, and no pricing.

Everything in [§2](#2-what-is-built-today) is implemented and running. Everything in [§4](#4-mvp-target-architecture) is not yet built. [§6](#6-gap-analysis) is the distance between them.

---

## 2. What is built today

```
room image + furniture class names
  → Grounding DINO   (text → boxes)
  → SAM 2.1 Tiny     (boxes → masks)
  → Depth Anything V2 (image → metric depth; FOV/EXIF focal length)
  → Open3D           (masked depth → point cloud → oriented bounding box)
  → per-object dimensions and visible volume
```

Four stages run sequentially in `moveai_prototype/pipeline.py`, driven either by a Streamlit UI (`app.py`) or a CLI smoke test (`smoke_test.py`). Tuning constants live in one frozen dataclass, `PipelineConfig` (`config.py:31`).

### Input preparation

`prepare_image` (`pipeline.py`) applies EXIF transpose, converts to RGB, and downscales with LANCZOS so the longest side is at most 1280 px. The cap bounds depth-model memory footprint, which dominates the run.

### Stage 1 — Grounding DINO: language to boxes

`detect_furniture` (`models.py:85`) runs `IDEA-Research/grounding-dino-tiny` for zero-shot text-conditioned detection. The customer-supplied class list becomes the text prompt, so detection vocabulary is controlled at request time rather than baked into trained weights — the reason a zero-shot detector was chosen over a fixed-class model.

Post-processing applies `box_threshold=0.30` and `text_threshold=0.25`, then `_class_aware_nms` (`models.py:70`) at IoU 0.50. The NMS is deliberately **class-aware**: it suppresses overlapping boxes only when they carry the same label, so a lamp standing in front of a sofa survives instead of being merged away. Results are truncated to `max_detections=8`.

### Stage 2 — SAM 2.1 Tiny: boxes to masks

`segment_detections` (`models.py:133`) prompts `facebook/sam2.1-hiera-tiny` with every detection box in a single batch, with `multimask_output=False` — one mask per box, no ambiguity resolution step. Masks are post-processed back to the original image size and attached to their `Detection`.

A mask rather than a box is what makes the geometry stage viable: back-projecting a rectangular box would pull in wall and floor pixels behind the object and inflate its depth extent.

### Stage 3 — Depth Anything V2: metric depth from one uncalibrated photo

`estimate_metric_depth` (`models.py`) loads `depth-anything/Depth-Anything-V2-Metric-Indoor-Large-hf` via Hugging Face Transformers and returns a metric depth map in meters.

Focal length is **not** predicted by this model. It is taken from EXIF `FocalLengthIn35mmFilm` when present; otherwise an assumed horizontal FOV (default 60°) converts image width into `focal_length_px` for the pinhole back-projection in Open3D. This replaces the previous Apple Depth Pro stage, which predicted both depth and focal length from `checkpoints/depth_pro.pt`.

### Stage 4 — Open3D: depth to bounding box

`geometry.py` converts each masked depth region into a fitted box.

`_masked_point_cloud` (`geometry.py:53`) back-projects with a pinhole model, using the predicted focal length and **assuming the principal point is the image center** (`geometry.py:89-91`) — true enough for uncropped phone photos, wrong for cropped or heavily edited ones. Points are produced in a camera-frame coordinate system: +x right, +y up, +z away from the camera.

Filtering happens in three passes, each for a distinct failure mode:

| Filter | Purpose |
|---|---|
| Depth clamp to `[0.20, 12.0]` m | Discards sensor-implausible depths outright |
| 5–95% quantile band within the mask | Removes background bleed where the mask spills past the object edge |
| Statistical outlier removal (20 neighbours, 2.0 σ) | Removes speckle that would stretch the fitted box |

The cloud is subsampled to at most 12,000 points, then `get_minimal_oriented_bounding_box(robust=True)` fits the box. If that fails, the code falls back to an axis-aligned box and records the substitution in the measurement's `warning` string (`geometry.py:172-180`) — the fallback is never silent.

Volume is the product of the box extents.

### Cross-cutting decisions

**Device selection.** `best_device()` (`models.py:36`) prefers MPS, then CUDA, then CPU, with `PYTORCH_ENABLE_MPS_FALLBACK=1` set at import so unsupported ops degrade to CPU instead of crashing.

**Load-infer-release per stage.** Every stage constructs its model, runs, then calls `release_memory()` (`models.py:44`), which drops references, forces a GC pass, and empties the accelerator cache. No model stays resident between stages.

This is an intentional concession to the 8 GB unified-memory machine the prototype was built on — the three models cannot coexist there. It is *also* why a full run takes roughly three minutes, most of it spent loading weights rather than computing. It is a known tradeoff, correct for a demo and the first thing that must change for the MVP.

**Per-object error isolation.** `measure_all` (`geometry.py:204`) catches per-object failures and collects them into `measurement_errors` rather than aborting. One un-measurable object degrades the inventory; it does not destroy the run.

**Network at first load.** Grounding DINO and SAM 2 still prefer `local_files_only=True` once cached. Depth Anything V2 loads from Hugging Face on first use (then hits the local HF cache).

---

## 3. Known limitations of the current measurement

**The single-view error is anisotropic, not uniform.** The fitted box contains only surfaces visible from one camera position, but the error this introduces is not spread evenly across the three axes. A frontal photo measures an object's *frontal* extents — length and height — reasonably well, because those edges are directly visible. It measures *depth* badly, because the far side, underside, and any occluded surface are never reconstructed: a sofa shot head-on can fit a box barely 0.2 m deep against a true depth near 0.9 m. Every measurement therefore carries a standing warning (`geometry.py:168`), and the number is not a quote-ready transport volume.

This matters beyond "the number is wrong": depth is also the axis with the *least* variation across a furniture class (sofas run roughly 0.85–1.0 m deep regardless of style, while length ranges 1.5–3.5 m). That means the specific axis a single photo measures worst is the one a class-specific prior can best replace — see [§4](#4-mvp-target-architecture) and [§5b](#5b-confidence-and-human-review-rules).

**~~Axis semantics are discarded.~~ Fixed.** `ObjectMeasurement` used to sort the three extents descending, discarding which was width, height, or depth. It now exposes named `width_m`/`height_m`/`depth_m` fields, classified by each fitted box axis's alignment with the camera frame (depth ≈ camera-forward, height ≈ up) — see `IMPLEMENTATION_ROADMAP.md` Build 1. This unblocks the anisotropic-error handling above (a prior can now target `depth_m` specifically) and the shell-ratio/truck-recommendation reasoning in §5b/§5c, which both depend on knowing which extent is which.

**Total volume is a naive sum.** `total_visible_volume_m3` (`pipeline.py:36`) adds per-object box volumes with no packing factor, no void allowance, no handling of overlapping or nested boxes, and no disassembly assumptions. Real transport volume is not the sum of bounding boxes.

**Subsampling is raster-ordered.** Points are decimated with `np.linspace` over pixels in scan order (`geometry.py:81-87`) rather than randomly, introducing a mild spatial bias on large objects.

**Recall depends on the prompt.** An item whose category is not in the class list is never detected, and nothing signals its absence. Acceptable when a presenter drives the demo; unacceptable when the output is a price.

**There is no notion of small items.** Every detection, regardless of size, is measured and reported identically. In a real household move, boxed goods (books, kitchenware, clothing) typically make up roughly half of total volume and carry the highest labour-per-volume of anything moved — yet nothing here distinguishes "measure this precisely" from "this is bulk goods, estimate it." There is also no boxed-goods path at all: no way to represent "40 boxes" as an inventory line.

---

## 4. MVP target architecture

### Component flow

```
intake form ─┐
             ├→ capture (video / photo walkthrough)
             │    → ingestion & keyframe selection
             │      → per-frame perception  (detect → segment → depth)
             │        → cross-frame fusion & object identity
             │          → room segmentation & assignment
             │            → class-priors table  (plausibility bounds · occluded-axis substitution · box-count ratios)
             │            → boxed-goods estimator  (seeded from detected storage + room count/type)
             │              → inventory assembly
             │                → customer review & amendment loop
             └────────────────→ quote & truck recommendation
                                 → booking request queue
                                   → company review console
```

The current pipeline becomes the **per-frame perception** box. Everything else is new.

The **class-priors table** is a single artifact serving three distinct jobs: bounding what a plausible dimension looks like per furniture class ([§5b](#5b-confidence-and-human-review-rules)), substituting a value for an axis a photo can't see ([§4](#4-mvp-target-architecture) below), and seeding expected box counts for detected storage furniture ([§5c](#5c-volume--quote-contract)). Building it once and using it three ways keeps those three policies from drifting apart.

### The hard sub-problems

Video walkthrough serves two different goals that this doc previously bundled together as one "multi-view fusion" problem: **coverage** (finding every object, grouping them by room) and **precision** (getting a better volume than one photo gives). Coverage requires video. Precision, it turns out, mostly doesn't — see the anisotropic-error discussion in [§3](#3-known-limitations-of-the-current-measurement): a photo already measures an object's high-variance axes (length, height) well, and the one axis it measures badly (depth) is exactly the axis a class prior predicts best. That demotes true multi-view fusion (structure-from-motion, pose estimation, 3D scene accumulation) from a critical-path requirement to a later precision upgrade, worth revisiting once real jobs are compared against actual moved volume ([Calibration](#calibration)).

The problems below are stated as requirements with candidate approaches; **no model or vendor is committed to yet**, and that choice should be made against measured results rather than in this document.

**Keyframe selection.** A walkthrough video is thousands of frames; perception is far too expensive to run on all of them. The system must choose a subset that covers every object from enough distinct viewpoints — for detection and room coverage, not for per-object 3D fusion. Candidates range from cheap signals (motion and blur scoring, fixed-interval sampling) to coverage-driven selection that keeps adding frames until each tracked object has been seen clearly at least once. The tradeoff is GPU cost against recall, and it is the main lever on per-job unit economics.

**Cross-frame object identity.** One physical sofa appearing in forty frames must become one inventory line. This is the problem with the worst failure modes in the whole system, and they are asymmetric: **splitting** one object into two inflates the quote and loses the customer, while **merging** two identical dining chairs into one under-quotes and costs the company on moving day. Association can lean on appearance embeddings, on rough 3D position (even without full pose recovery, approximate position from frame-to-frame tracking helps), or on simple frame-to-frame tracking — position-based association is generally stronger here precisely because furniture in the same room is often visually identical.

**Room segmentation and assignment.** The inventory must group by room, which requires deciding where one room ends and the next begins in a continuous walkthrough, and giving each a human-meaningful label. Doorway transitions are detectable both visually and from the camera trajectory; labelling is a scene-classification problem, and may be better solved by simply asking the customer to confirm room names than by inferring them.

**Open-vocabulary inventory.** Recall must stop depending on the customer naming categories correctly. The detector needs to enumerate movable objects on its own, with the class list becoming a prior rather than a filter. This also changes the error surface: the system will start finding things the customer does not intend to move, making the step-3 review loop load-bearing rather than a formality.

**Deferred: true multi-view fusion.** Accumulating multiple views into one 3D reconstruction (via device sensor pose — ARKit/ARCore — or structure-from-motion) remains the eventual path to a defensible volume beyond what priors approximate. It is not required for the MVP and should be picked up once prior-based estimates have been measured against real outcomes and shown to need it.

---

## 5. Behavior contracts

These are the invariants that must hold across both the current pipeline and everything added later. They exist because the components will be built at different times, and because the output carries financial consequences.

### 5a. Inter-stage data schemas

Today the pipeline passes in-memory dataclasses holding raw NumPy arrays — `Detection` (`models.py:29`), `ObjectMeasurement` (`geometry.py:30`), `PipelineResult` (`pipeline.py:26`) — and the only serialized artifact is the flattened JSON inventory built by `result_rows` (`app.py:60`). That is sufficient for a single-process demo and insufficient for a system where frames are processed independently, possibly out of order, and results are stored and revisited.

**Global conventions, stated once and enforced everywhere:**

- All lengths in **metres**, all volumes in **cubic metres**. Imperial units are a presentation concern only and never enter a stored payload.
- Point coordinates are camera-frame: **+x right, +y up, +z away from camera** (`geometry.py:91-93`). Any world-frame data must be explicitly labelled as such.
- Every confidence is a `[0, 1]` float, and the signal it came from is named. There is no bare "score" field.

**Required payload boundaries:**

| Boundary | Must carry |
|---|---|
| Capture → ingestion | Media reference, capture timestamp, device intrinsics/pose if available (and an explicit flag when not) |
| Ingestion → perception | Frame identity, source offset, selection reason |
| Perception → observation | One record per detected object per frame: label, detection confidence, mask reference, frame provenance |
| Observation → fused object | Stable object ID, **the full list of contributing frames**, per-view measurements, fused dimensions, agreement across views |
| Fused object → inventory item | Customer-facing label, room assignment, dimensions with named axes, volume with uncertainty, review state |
| Inventory item → quote line | Volume contribution, access factors applied, resulting price component |

Two requirements deserve emphasis. **Provenance is mandatory** — every fused object must name the frames it came from, because when a customer disputes an item, the answer is showing them the frames it was measured in. And **object identity must be stable across reprocessing**, since the customer amends an inventory that has already been shown to them.

**`measurement_basis`.** Every inventory item carries one of three values, and it must survive unchanged from the item all the way to its quote line, because the surcharge contract in [§5c](#5c-volume--quote-contract) keys on it:

- `measured` — dimensions came from direct observation with no prior substitution.
- `prior_assisted` — one or more axes (typically the occluded depth axis) were filled from the class-priors table rather than observed directly.
- `declared` — the line has no underlying detection at all: a customer-entered item, or a boxed-goods line seeded from storage-furniture counts and adjusted by the customer.

**Boxed-goods lines are a distinct line type, not an object measurement.** They carry a box-equivalent count and the seed that produced it (which storage furniture and room counts contributed), not a set of dimensions — there is no OBB to report. See [§5c](#5c-volume--quote-contract) for how this line enters the quote.

**Below-floor detections are evidence, not inventory.** Objects too small to measure reliably (see [§5b](#5b-confidence-and-human-review-rules)) do not become inventory lines and are never silently included in `total_visible_volume_m3`-style totals — but they aren't discarded either. They pass through the payload as density evidence (count and rough location) that feeds the boxed-goods seed: a cluttered kitchen counter is itself a signal that there are more boxes than an empty one.

### 5b. Confidence and human-review rules

The prototype attaches the same warning string to every measurement and lists failures under "Objects requiring human review" (`app.py:234-236`). That is a UI convention, not a policy. The MVP needs named states with defined transitions.

Every inventory item resolves to exactly one of three states:

- **Auto-accept** — flows into the quote without intervention.
- **Customer-confirm** — surfaced in the step-3 review loop for the customer to verify, correct, or remove.
- **Staff-escalate** — the booking cannot be auto-quoted; it enters the company queue with the reason attached.

Signals that drive state, all of which must be recorded on the item rather than recomputed at display time:

| Signal | Available today |
|---|---|
| Detection confidence | Yes — `Detection.score` |
| Point count supporting the measurement | Yes — `ObjectMeasurement.point_count` |
| Axis-aligned fallback fired | Yes — `ObjectMeasurement.used_axis_aligned_fallback` (`geometry.py:30`), a direct boolean since Build 1, no longer parsed from `warning` text |
| **Shell ratio** — `depth_m` vs. class-expected depth | Yes — compares `ObjectMeasurement.depth_m` (named directly since Build 1's axis-semantics fix, `geometry.py:108-131`) against the class-priors table; a sofa fitted at 0.2 m deep against an ~0.9 m expectation is a front-facing shell, not a real measurement |
| **Border truncation** — mask touches an image edge | Yes — a check against `detection.mask`'s boundary rows/columns (`models.py:160-161`), no new inference required |
| Dimensions implausible for the class (any axis, not just depth) | Partially — needs the class-priors table populated; the check itself is a comparison against `width_m`/`height_m`/`depth_m` |
| Disagreement across views | No — needs multi-view fusion, deferred per [§4](#4-mvp-target-architecture) |

**The interrupt rule: flag only implausibility, never mere imperfection.** `prior_assisted` alone — an occluded axis quietly filled from the priors table — does **not** trigger customer-confirm. Only a shell ratio, border truncation, or implausible dimension does. Every customer prompt is a chance to abandon the flow mid-capture, and low friction is this product's core advantage over a manual survey; a measurement that is merely *typical-but-unverified* is exactly what a human surveyor would also eyeball and accept. When a plausibility flag does fire, the customer sees a single proposed number to confirm ("we measured this sofa at about 2.1 m long — is that right?"), not a request to re-capture.

Two rules are non-negotiable regardless of how the thresholds are eventually tuned. **A failed measurement is never silently dropped** — the current `measurement_errors` behaviour (`geometry.py:223-224`) becomes an escalation, not a log line, because an object that failed to measure is still an object that must be moved. And **the customer confirming an item does not clear a staff escalation**; the two review paths are independent, since the customer cannot assess whether a measurement is geometrically sound.

This second rule also settles which state a signal drives (`IMPLEMENTATION_ROADMAP.md` Build 5): border truncation and low detection confidence are things a plain-language question can resolve ("is this ~2.1 m long?", "is this really a sofa?"), so they drive customer-confirm as above. Axis-aligned fallback and a low supporting point count are judgments about geometric soundness the customer has no basis to make, so they route to staff-escalate instead of a customer prompt — they are additional signals within the *escalation* half of this section's rule, not new customer-confirm triggers alongside shell ratio/border/implausible-dimension.

**Booking lifecycle (`IMPLEMENTATION_ROADMAP.md` Build 7).** A flagged job — an unconfirmed `customer_confirm` item, an escalated item, an unmeasured item, or an oversize/multi-trip truck — is still allowed to *request* a booking; §5c below already establishes that these cost a staff review, not money, and requiring the customer to fully resolve every flag before requesting would just add friction back into a product built to remove it. What a request cannot do is submit against a quote that no longer reflects the current inventory: the Quote page auto-persists only its first version and otherwise waits for an explicit customer action to regenerate, so a customer can reach the booking step with a stale active quote without ever having seen a wrong number themselves. The booking step blocks in that case and sends the customer back to Quote, rather than silently regenerating a version on their behalf or pinning a price they didn't see. A submitted request enters the company queue as `pending_staff_review`; the job itself only advances to `booked` once staff confirm it, keeping that status meaning "the company accepted this job," not "the customer asked for it."

### 5c. Volume → quote contract

**The prototype originally produced no pricing at all, and that was deliberate rather than unfinished** — presenting a simulated price on top of a single-view lower bound would have attached a credible-looking number to a measurement known to be biased low. The pricing engine (`moveai_prototype/pricing.py`, `boxed_goods.py`, `priors.py` — see `IMPLEMENTATION_ROADMAP.md` Build 3) now exists and satisfies the contract below, seeded with Hong Kong market research rather than invented figures — see Build 3's roadmap notes for sources.

The contract this layer must satisfy:

**Volume is an input, not the output.** The quote is a function of estimated volume, the access factors from intake (origin and destination floor, lift availability, parking distance), and company-specific pricing configuration. Access factors are labour multipliers and must apply independently of volume — carrying the same sofa to a fourth floor without a lift is not the same job as carrying it to the ground floor.

**Quote from the upper bound of the estimate, once — never stack margin.** Priors ([§4](#4-mvp-target-architecture)) exist to produce a *typical* estimate per object; the quoting layer is the one place that adds conservatism on top, by pricing from the upper end of the resulting volume range rather than its midpoint. This is a hard constraint, not a suggestion: margin must be applied in exactly this one configurable place. If the priors table itself is padded "to be safe," and the quoting layer adds margin again, and truck sizing rounds up again, the stacked effect prices the company out of jobs it should win. Each layer states its own number honestly; only the quoting policy decides how much conservatism the customer-facing price carries.

**The surcharge contract fires on declared quantities being wrong, not on measurement error.** These are different failures and this product can only stand behind one of them. If a scanned, `measured` or `prior_assisted` item turns out larger on moving day, that is the system's estimation error, and the company absorbs it — that's what the upper-bound margin above is for. If a `declared` item — a boxed-goods count or a manually-entered object the customer supplied — turns out wrong, the day-of surcharge applies, because the customer supplied that number, not the pipeline. "You told us 40 boxes and there were 70" is a defensible conversation with a customer; "our camera underestimated your sofa" is not, and would undermine the entire premise of a measured quote. This is exactly why `measurement_basis` ([§5a](#5a-inter-stage-data-schemas)) must reach the quote line unchanged — it is the field the surcharge policy branches on.

**Boxed goods are a quote line with labour weighted separately from volume.** Forty boxes down four flights of stairs without a lift is a materially different job from one sofa of equal volume, even though the volume-based portion of the quote is identical — the boxed-goods line needs its own labour multiplier in the pricing configuration, not just its own volume figure. See [§4](#4-mvp-target-architecture) for how the box count itself is seeded and confirmed.

**Containers are assumed to move empty; declared contents become their own boxed-goods lines.** A wardrobe or cabinet's *contents* are invisible to any camera angle by construction, so the volume estimate for the container itself assumes it travels emptied, and the customer separately declares what's inside as boxed goods. Flagging this as an assumption to validate against partner companies' actual practice, not a settled decision — see [Calibration](#calibration).

**Truck recommendation is a separate function from price.** It depends on packed volume and on the largest single dimension — a wardrobe that fits the volume budget but not the door. It therefore requires the named-axis dimensions that §3 notes are currently discarded.

**Quotes are versioned against the inventory that produced them.** When a customer amends the inventory, the previous quote is superseded, not mutated, so the company can see what was originally offered.

**An unconfirmed customer-confirm flag costs a staff review, not money (`IMPLEMENTATION_ROADMAP.md` Build 6).** A customer can reach the Quote page with items still flagged for confirmation (`DESIGN.md` §5b) — most commonly the seeded boxed-goods line, deliberately seeded unconfirmed per Build 5. This does not make those items surcharge-eligible: the upper-bound margin above already prices the risk of a `measured`/`prior_assisted` item being wrong, so charging a surcharge on top of that margin would charge for the insurance and then decline the claim — the same stacking this section already forbids elsewhere. The surcharge instead targets a customer misstating a quantity they supplied (a declared box count, a manually-entered item, a corrected measurement); failing to review our own camera's work is inattention, not the kind of dishonesty the surcharge is meant to price. So an unconfirmed flag is warned about prominently and costs nothing — it instead marks the job as needing a staff look before the booking is accepted, keeping the "measured quote, no surprises" premise intact.

### Calibration

Every number introduced above — class-prior dimensions, box-count-per-storage-item ratios, and the upper-bound margin itself — is currently reasoned from general moving-industry rules of thumb, not measured data, because no multi-view fusion exists yet to compare against ground truth. Partner moving companies already hold the actual calibration set: historical job records pairing an initial estimate against the volume and labour a job actually took. Any of the figures in this document should be treated as a starting point to be overridden by that data as soon as it's available, not as a fixed specification.

---

## 6. Gap analysis

| Capability | Today | MVP requirement | What has to change |
|---|---|---|---|
| **Input** | One prepared still image, ≤1280 px | Video or multi-photo walkthrough | Ingestion, keyframe selection, per-frame batching |
| **Object discovery** | Customer-supplied class list; unlisted items invisible | Automatic enumeration of movable objects | Open-vocabulary detection; class list becomes a prior |
| **Object identity** | None — each detection independent | One physical object = one inventory line | Cross-frame association; stable IDs surviving reprocessing |
| **Room awareness** | None | Inventory grouped and labelled by room | Room segmentation from trajectory; customer-confirmed labels |
| **Volume fidelity** | Single-view visible-surface lower bound, anisotropic error, no class priors | Defensible transport volume | Class-priors table for occluded-axis substitution (critical path); true multi-view fusion deferred until measured against outcomes |
| **Dimensions** | ~~Three unordered edge lengths~~ Named `width_m`/`height_m`/`depth_m` — **done, `IMPLEMENTATION_ROADMAP.md` Build 1** | Named width / height / depth | Done |
| **Small items** | None — every detection measured and reported identically | Size floor below which items become density evidence, not inventory lines | Floor threshold; evidence feeds boxed-goods seed instead of being measured or discarded |
| **Boxed goods** | ~~No representation at all~~ Seeded, customer-adjustable line — **done, `IMPLEMENTATION_ROADMAP.md` Build 5** | Seeded box-equivalent line from detected storage + room count/type, customer-adjusted | Done |
| **Latency** | ~3 min/image; models loaded and freed per stage | Interactive turnaround on a full walkthrough | Resident models on adequate GPU; batching; the 8 GB constraint no longer applies |
| **Persistence** | ~~None (in-memory, lost on rerun)~~ Schema + job spine + inventory-review amendments + versioned quotes + booking requests wired into the UI — **done, `IMPLEMENTATION_ROADMAP.md` Builds 2, 4, 5, 6 & 7** | Jobs, inventories, amendments, quotes, bookings all durable | Done |
| **Review policy** | ~~Blanket warning on every item; errors listed in an expander~~ Three named states wired into inventory persistence and a review page — **done, `IMPLEMENTATION_ROADMAP.md` Build 5** | Three named states, fired only by implausibility | Per-class plausibility ranges (shell ratio, implausible dimension) once `priors.py`'s stubs are populated |
| **Pricing** | ~~None (intentionally)~~ Engine implemented and wired into a Quote page — **done, `IMPLEMENTATION_ROADMAP.md` Builds 3 & 6** | Upper-bound quote + truck recommendation; surcharge scoped to declared-quantity error | Done |

The rows are roughly ordered by dependency: identity and fusion unlock volume fidelity, which is what makes pricing defensible.

---

## Related documents

- [`moveai_prototype/README.md`](moveai_prototype/README.md) — how to run the prototype and its demo path.
- [`demo_images_100/README.md`](demo_images_100/README.md), [`real_world_samples/README.md`](real_world_samples/README.md) — sample dataset provenance and licensing.
