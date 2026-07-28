"""FastAPI backend wrapping the existing intake/inventory/quote/booking/
console business logic (IMPLEMENTATION_ROADMAP.md Build 8), plus the AI
pipeline behind `/api/jobs/{job_id}/capture` (Build 10) -- the existing
`db.py`/`inventory_sync.py`/`quote_sync.py`/`booking_sync.py`/`pricing.py`/
`pipeline.py` logic is reused unchanged, only wired to HTTP.

Run from `moveai_prototype/`:
    uvicorn backend.main:app --reload
"""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

import db  # noqa: E402
from backend.routers import (  # noqa: E402
    booking,
    capture,
    console,
    intake,
    inventory,
    jobs,
    quote,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = db.connect()
    db.initialize(conn)
    app.state.conn = conn
    yield
    conn.close()


app = FastAPI(title="MoveAI backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs.router)
app.include_router(intake.router)
app.include_router(inventory.router)
app.include_router(quote.router)
app.include_router(booking.router)
app.include_router(console.router)
app.include_router(capture.router)
