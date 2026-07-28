"""Shared FastAPI dependencies: one process-wide SQLite connection and a
lock serializing every request against it, mirroring how `job_context.py`'s
`st.cache_resource` gives the Streamlit app a single shared connection
(IMPLEMENTATION_ROADMAP.md Build 8).

`db.py` takes a bare `sqlite3.Connection` and expects the caller to
serialize access -- Streamlit gets this for free since a session is
single-threaded, but FastAPI runs sync path functions across threadpool
threads. `db.connect()` sets `check_same_thread=False`, which only disables
Python's same-thread guard -- it does not make a single `sqlite3.Connection`
object safe for *concurrent* use from multiple threads. A first attempt at
this module locked only mutating calls and left reads unguarded; a
concurrent-request test (`GET`/`POST` racing on the same connection object)
produced `sqlite3.InterfaceError: bad parameter or other API misuse` and
even spurious 404s, not just the `database is locked` error the roadmap
anticipated. Fixed by having `get_conn` hold `db_lock` for the entire
request via a generator dependency, serializing all access -- reads
included -- rather than locking only writes. Sufficient for the single-user
demo load this build targets; a real multi-connection pool is out of scope.
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import Iterator

BACKEND_DIR = Path(__file__).resolve().parent
APP_DIR = BACKEND_DIR.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import sqlite3  # noqa: E402

from fastapi import Depends, HTTPException, Request  # noqa: E402

import db  # noqa: E402

db_lock = threading.Lock()


def get_conn(request: Request) -> Iterator[sqlite3.Connection]:
    with db_lock:
        yield request.app.state.conn


def get_job_or_404(
    job_id: int, conn: sqlite3.Connection = Depends(get_conn)
) -> dict:
    job = db.get_job(conn, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"No job with id {job_id!r}")
    return job
