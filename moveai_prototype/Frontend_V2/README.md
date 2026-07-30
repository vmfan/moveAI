# Move AI Streamlit + FastAPI backend

The two Streamlit apps now communicate with the supplied MoveAI FastAPI backend.

## Configuration

The frontend defaults to:

```text
http://localhost:8010
```

Override it with:

```bash
export MOVEAI_API_BASE=http://localhost:8010
```

The client (`backend_client.py`) calls fixed, hard-coded routes matching `../API_REFERENCE.md` / `../API_REFERENCE_openapi.json` — job, intake, upload, capture, inventory, quote, booking, console, and staff-decision endpoints.

## Install

```bash
cd move_ai_streamlit_backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Start backend

From `moveai_prototype/`:

```bash
uvicorn backend.main:app --reload --port 8010
```

Verify:

```text
http://localhost:8010/docs
```

## Start customer app

```bash
streamlit run move_ai.py --server.port 8501
```

## Start administrator app

In a second terminal:

```bash
streamlit run administrator.py --server.port 8502
```

## Integrated flow

1. Creates a backend job.
2. Sends `IntakeIn` data.
3. Uploads selected images via `POST /capture/uploads`.
4. Calls capture with `CaptureIn.image_names`.
5. Reads persisted backend inventory.
6. Adds manual furniture using `DeclaredItemIn`, including dimensions.
7. Requests the backend quote.
8. Submits the booking.
9. Administrator reads backend console jobs and sends `StaffDecisionIn`.

Backend errors (4xx/5xx) surface in the UI with the status code and response detail.
