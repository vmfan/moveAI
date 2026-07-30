# MoveAI

MoveAI replaces manual move-quoting with a self-serve flow: a customer answers a
short intake form, captures photos of their space, and the system produces a
measured inventory and a priced quote. `DESIGN.md` covers the product vision and
the inter-stage contracts; `IMPLEMENTATION_ROADMAP.md` is the authoritative,
per-build history of what's actually implemented and its current status — trust
it over any prose summary here if the two ever disagree.

This file is the practical entry point: how to run the app on one machine, how
to reach it from a phone on the same WiFi, and what would additionally be
needed to reach it from a genuinely different network.

## Repo layout

```
DESIGN.md                      product vision + inter-stage contracts
IMPLEMENTATION_ROADMAP.md       per-build history and status (source of truth)
real_world_samples/images/      sample room photos used by the Capture UI's sample picker
moveai_prototype/
  backend/                     FastAPI app — routers wrap the business logic below over HTTP
  frontend/                    Next.js (App Router) UI
  *.py                         business logic (db.py, pricing.py, inventory_sync.py, pipeline.py, ...)
                                — reused unchanged by the FastAPI backend
  app.py, pages/               legacy Streamlit UI (phase-1 MVP, still runnable standalone)
  README.md                    Streamlit-app-specific notes (model checkpoints, technical limitations)
  API_REFERENCE.md             hand-written companion to the backend's OpenAPI schema
```

## Prerequisites

- **Python 3.12**, already provisioned in `moveai_prototype/.venv` — pins are in
  `moveai_prototype/requirements.txt` if you need to rebuild the venv.
- **Node/npm** for `moveai_prototype/frontend/`.
- **Model weights:**
  - Grounding DINO (`IDEA-Research/grounding-dino-tiny`) and SAM 2 (`facebook/sam2.1-hiera-tiny`) are pulled through the Hugging Face cache automatically.
  - Depth Anything V2 Metric Indoor Large (`depth-anything/Depth-Anything-V2-Metric-Indoor-Large-hf`) is also pulled through Hugging Face (no manual Depth Pro `.pt` download).
- **`.env` secrets** (`moveai_prototype/.env`): `HKUST_VLM_API_KEY` and `HKUST_VLM_BASE_URL`, used by the cross-image dedup/room-labeling pass (`backend/reasoning_client.py`). The capture pipeline still works without these — a missing/unreachable dedup call is surfaced as a non-fatal `dedup_error` in the capture response, not a hard failure.

## Quick start — same machine

From `moveai_prototype/`:

```bash
# backend
.venv/bin/python -m uvicorn backend.main:app --port 8000

# frontend (separate terminal)
cd frontend && npm run dev
```

Open `http://localhost:3000`.

**If port 8000 or 3000 is already taken** (common on a dev machine with other
local services running — this project's own build history repeatedly hit this
and fell back to alternate ports), just pick different ones:

```bash
.venv/bin/python -m uvicorn backend.main:app --port 8010
```

```bash
NEXT_PUBLIC_API_BASE=http://localhost:8010 npm run dev -- -p 3002
```

`NEXT_PUBLIC_API_BASE` defaults to whatever's in `frontend/.env.local` — override
it on the command line any time the backend isn't on that default port.

## Testing from a phone/tablet on the same WiFi

The Mac and the phone must be on the **same WiFi network** (not a guest/isolated
network — some routers keep guest-network clients from reaching each other).

1. **Find the Mac's LAN IP** (this changes per network, so re-check it each time you switch WiFi):
   ```bash
   ipconfig getifaddr en0
   ```
2. **Start the backend bound to all interfaces**, not just localhost:
   ```bash
   .venv/bin/python -m uvicorn backend.main:app --host 0.0.0.0 --port 8010
   ```
3. **Start the frontend pointed at the Mac's LAN IP**, not `localhost` — the phone's browser loads this JS bundle and needs an address it can actually reach:
   ```bash
   NEXT_PUBLIC_API_BASE=http://<lan-ip>:8010 npm run dev -- -p 3002
   ```
4. **On the phone**, open `http://<lan-ip>:3002` in a browser.

**If it still doesn't work:** check the Mac's firewall isn't blocking inbound
connections on the ports above (System Settings → Network → Firewall), and look
at the actual browser-side error via Safari's remote Web Inspector — enable
Safari → Settings → Advanced → "Show Develop menu" on the Mac, and Settings →
Safari → Advanced → Web Inspector on the iPhone, then Develop menu → [iPhone
name] → the page, on the Mac.

## Going remote (a genuinely different network)

Not set up in this repo today. To reach the app from a network that isn't the
same LAN, you'd need one of:

- a tunnel (ngrok, Cloudflare Tunnel, Tailscale Funnel) pointed at the locally-running backend, or
- an actual deployment (cloud VM, Render/Fly/Railway, etc.) with a real domain.

Either way, the only things that change are configuration, not application
code — confirming the upload feature (`IMPLEMENTATION_ROADMAP.md` Build 13) is
already decoupled from "the server lives next to the client":

- `NEXT_PUBLIC_API_BASE` points at the real public URL instead of a LAN IP.
- CORS (`backend/main.py`) allows that real origin instead of (or in addition to) the LAN-IP regex.
- HTTPS becomes effectively required once a public tunnel/host sits in front — browsers block a mixed-content `fetch` from an HTTPS page to a plain HTTP API, and most tunnel providers terminate TLS for you automatically.

## Running the test suite

No model weights needed except where noted, from `moveai_prototype/`:

```bash
.venv/bin/python db_smoke_test.py
.venv/bin/python pricing_smoke_test.py
.venv/bin/python job_flow_smoke_test.py
.venv/bin/python inventory_review_smoke_test.py
.venv/bin/python quote_smoke_test.py
.venv/bin/python booking_smoke_test.py
.venv/bin/python dedup_smoke_test.py
.venv/bin/python pipeline_runtime_smoke_test.py   # needs Grounding DINO/SAM2/Depth Anything V2 cached
```

## The legacy Streamlit app

`streamlit run app.py` (from `moveai_prototype/`) still runs standalone — it's
the phase-1 MVP that predates the FastAPI+Next.js stack above, and is superseded
by it for the current demo/grading path. See `moveai_prototype/README.md` for
Streamlit-specific run instructions.

## Where to look next

- `DESIGN.md` — product vision, target workflow, inter-stage contracts.
- `IMPLEMENTATION_ROADMAP.md` — per-build history and current status.
- `moveai_prototype/API_REFERENCE.md` — backend endpoint reference (plus the live `/docs` and `/redoc` Swagger/ReDoc UIs once the backend is running).
