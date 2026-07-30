from __future__ import annotations

from fastapi import APIRouter

from backend import ors_client

router = APIRouter(prefix="/api/geocode", tags=["geocode"])


@router.get("/autocomplete")
def autocomplete(q: str) -> list[dict]:
    """Address suggestions for `q`. Returns `[]` (never a 5xx) if ORS is
    unreachable or unconfigured -- the frontend just shows no suggestions
    and the user keeps typing free text, identical to today's behavior.
    """
    if len(q.strip()) < 3:
        return []
    try:
        return ors_client.autocomplete(q)
    except ors_client.OrsClientError:
        return []
