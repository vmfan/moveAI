# MoveAI Backend API Reference

This doc is a companion to `API_REFERENCE_openapi.json` (the machine-generated OpenAPI schema — authoritative for **routes, methods, path/query params, and request bodies**). Response bodies in this backend are plain dicts, not Pydantic models, so they don't show up in the OpenAPI schema — this file documents the shapes by hand, from the actual router code.

For live, always-in-sync exploration, run the backend and open:
- `http://localhost:<port>/docs` — Swagger UI
- `http://localhost:<port>/redoc` — ReDoc
- `http://localhost:<port>/openapi.json` — raw schema (same as the exported file here)

## Caveats — read before building against this API

- **No authentication or authorization on any endpoint**, including the staff-only booking-decision endpoint (`POST /api/console/bookings/{booking_id}/decision`). This is prototype-only behavior — don't design a security model around it, and don't assume any endpoint is protected.
- **CORS is locked to `http://localhost:<any port>`** (`main.py`). A frontend served from any other origin will need this widened before it can call the API from a browser.
- **The capture-pipeline artifact endpoints are backed by an in-memory, process-local cache**, not the database:
  - `GET /api/jobs/{job_id}/capture/images`
  - `GET /api/jobs/{job_id}/capture/overlay.png`
  - `GET /api/jobs/{job_id}/capture/depth.png`
  - `GET /api/jobs/{job_id}/capture/inventory`
  - `GET /api/jobs/{job_id}/capture/points/{item_index}`

  These all 404 after a backend restart, even though the job and its DB-persisted inventory (`GET /api/jobs/{job_id}/inventory`) survive fine. Don't rely on these for anything that needs to persist.
- `POST /api/jobs/{job_id}/capture` only accepts `image_names` that already exist as files in `real_world_samples/images/` — it's not an upload endpoint, and unknown names 404.
- The only backend-enforced step ordering is via `409` responses in the quote/booking routes when prerequisites (intake, pricing config, inventory items, a quote) are missing. The step gating in the current frontend (`lib/gating.ts`) is a **client-side UI convenience only** — it is not a backend contract. A new frontend is free to call any endpoint in any order; the backend will simply 409 if something required is missing.

## Endpoints

### Jobs — `/api/jobs`

**`POST /api/jobs`** — no body. Creates a job.
Response: job dict, e.g. `{"id": 1, "status": "intake", "created_at": "...", ...}` (see `db.get_job` for the full column set).

**`GET /api/jobs/{job_id}`** — Response: same job dict. 404 if job doesn't exist.

---

### Intake — `/api/jobs/{job_id}/intake`

**`PUT /api/jobs/{job_id}/intake`** — body: `IntakeIn` (see OpenAPI schema for full field list: contact info, origin/destination address + floor/lift/parking distance, room count, preferred move date).
- `422` with a list of validation error strings if intake data is invalid.
- On success, auto-advances job status `intake` → `capture`.
- Response: the saved intake dict (mirrors `IntakeIn` fields plus `job_id`).

**`GET /api/jobs/{job_id}/intake`** — Response: saved intake dict. `404` ("No intake saved for this job yet.") if none saved.

---

### Inventory — `/api/jobs/{job_id}/inventory`

**`GET /api/jobs/{job_id}/inventory`** — seeds boxed-goods rows from intake if not already present (requires an active pricing config — `409` otherwise).
Response:
```json
{
  "items": [ { "id": 1, "label": "...", "room_label": "...", "quantity": 1, "width_m": 0.0, "height_m": 0.0, "depth_m": 0.0, "confirmed": false, "source": "declared|captured|boxed_goods", "...": "..." } ],
  "summary": { "...": "aggregate volume/count fields" }
}
```

**`POST /api/jobs/{job_id}/inventory/declared`** — body: `DeclaredItemIn` (`label`, optional `room_label`, `quantity`, `width_m`/`height_m`/`depth_m`). Auto-advances status `capture` → `inventory_review`. Response: created item dict (same shape as one entry in `items` above).

**`POST /api/jobs/{job_id}/inventory/{item_id}/confirm`** — no body. Response: item dict with `confirmed: true`. `404` if item doesn't exist or belongs to another job.

**`POST /api/jobs/{job_id}/inventory/{item_id}/correct`** — body: `CorrectionIn` (`width_m`, `height_m`, `depth_m`, all required). Response: updated item dict. Same `404` behavior as confirm.

**`POST /api/jobs/{job_id}/inventory/boxed-goods/count`** — body: `BoxedGoodsCountIn` (`item_id`, `count`). Requires active pricing config (`409` otherwise); `404` if `item_id` isn't a boxed-goods item for this job. Response: updated item dict.

**`DELETE /api/jobs/{job_id}/inventory/{item_id}`** — Response: `{"deleted": true, "item_id": <id>}`. `404` as above.

---

### Quote — `/api/jobs/{job_id}/quote`

**`GET /api/jobs/{job_id}/quote`** — builds a fresh quote and compares it against the stored one (persists a new version if none exists yet). `409` if intake is missing, no active pricing config, or no inventory items.
Response:
```json
{
  "quote": { "...": "quote total/line-item breakdown fields" },
  "version": 1,
  "stale": false,
  "lines": [ { "...": "pricing line items" } ],
  "staff_review_reasons": ["..."]
}
```

**`POST /api/jobs/{job_id}/quote/regenerate`** — no body. Forces a new persisted quote version. Same `409`s as `GET`. Response: same shape as above, with `stale: false`.

**`GET /api/jobs/{job_id}/quote/versions`** — Response: list of past quote version dicts (each shaped like the `quote` field above, tagged with its `version`).

---

### Booking — `/api/jobs/{job_id}/booking`

**`GET /api/jobs/{job_id}/booking`** —
Response: `{"booking": <dict|null>, "blockers": ["..."]}`. If no quote exists yet, `blockers` is `["No quote has been generated yet."]`.

**`POST /api/jobs/{job_id}/booking/submit`** — body: `BookingSubmitIn` (`customer_note: str|None`). `409` with the list of blockers if booking isn't currently allowed (e.g. missing quote). Response: `{"booking": {...}, "created": true|false}`.

**`POST /api/jobs/{job_id}/booking/resubmit`** — body: `ResubmitIn` (`customer_note: str|None`). `404` if no booking exists for the job; `400` if resubmit isn't valid from the booking's current state. Response: updated booking dict.

---

### Console (staff-facing, not job-scoped) — `/api/console`

**`GET /api/console/bookings`** — query param `status` (optional). Response: list of booking row dicts for staff review (status, job info, customer note, etc.).

**`POST /api/console/bookings/{booking_id}/decision`** — body: `StaffDecisionIn` (`status`, optional `staff_note`). `404` if booking not found; `400` if the status transition is invalid. Response: updated booking dict.
> No auth gate — reachable by anyone with the URL.

---

### Capture (AI pipeline) — `/api/jobs/{job_id}/capture`

**`POST /api/jobs/{job_id}/capture`** — body: `CaptureIn` (`image_names: list[str]` required/non-empty, optional `furniture_classes`, `room_label`, `box_threshold`, `max_detections`). `image_names` must match files already in `real_world_samples/images/` (404 otherwise — not an upload endpoint). Auto-advances status `capture` → `inventory_review`. If ≥2 images are captured together, runs a cross-image dedup/room-labeling pass; failures there are captured into `dedup_error` rather than failing the whole request.
Response:
```json
{
  "images": {
    "<image_name>": {
      "...": "per-image capture summary fields",
      "timings_s": { "...": "stage timings" },
      "total_visible_volume_m3": 0.0
    }
  },
  "duplicates_removed": ["..."],
  "room_labels_assigned": { "...": "..." },
  "dedup_error": null,
  "artifacts": {
    "overlay_url_template": "...",
    "depth_url_template": "...",
    "inventory_url": "...",
    "point_cloud_url_template": "...",
    "images_url": "..."
  }
}
```

**`GET /api/jobs/{job_id}/capture/images`** — Response: `{"image_names": ["..."]}` (in-memory cache — see caveats).

**`GET /api/jobs/{job_id}/capture/overlay.png`** — query param `image_name` (required). Response: raw `image/png` bytes. `404` if that image hasn't been captured (or the process has restarted).

**`GET /api/jobs/{job_id}/capture/depth.png`** — query param `image_name` (required). Response: raw `image/png` bytes, same 404 behavior.

**`GET /api/jobs/{job_id}/capture/inventory`** — Response: merged inventory across every captured image for the job:
```json
{
  "items": [
    {
      "index": 1, "label": "...", "detection_confidence": 0.0,
      "width_m": 0.0, "height_m": 0.0, "depth_m": 0.0,
      "visible_obb_volume_m3": 0.0, "median_depth_m": 0.0,
      "point_count": 0, "used_axis_aligned_fallback": false,
      "mask_touches_border": false, "warning": null,
      "source_image_name": "..."
    }
  ],
  "errors": [ { "index": 1, "label": "...", "detection_confidence": 0.0, "message": "...", "source_image_name": "..." } ],
  "total_visible_volume_m3": 0.0,
  "timings_s": { "<image_name>": { "...": "stage timings" } }
}
```
Note the field rename: the pipeline's internal `detection_score` is exposed here as `detection_confidence`. `404` if nothing has been captured yet for the job.

**`GET /api/jobs/{job_id}/capture/points/{item_index}`** — path `item_index` (1-based), query `image_name` (required). Response: `application/json` Plotly figure JSON for that item's point cloud. `404` if `item_index` is out of range or nothing was captured for `image_name`.

---

### Samples — `/api/samples`

**`GET /api/samples`** — no params. Response: `[{"name": "...", "url": "/static/samples/..."}, ...]` listing available sample images that `POST /capture` can use.
