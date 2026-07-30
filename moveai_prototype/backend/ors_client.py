"""Thin client for the OpenRouteService (ORS) REST API, used to autocomplete
addresses and to compute depot-to-address driving distance for quote pricing.

Mirrors `reasoning_client.py`'s shape: a bare `httpx` wrapper (no SDK
dependency, since ORS is a plain REST API), a `_config()` env-var helper, and
a dedicated exception type callers must catch to degrade gracefully -- ORS
availability must never block intake or quote generation.
"""

from __future__ import annotations

import os

import httpx

DEFAULT_BASE_URL = "https://api.openrouteservice.org"
DEFAULT_TIMEOUT_S = 8.0


class OrsClientError(RuntimeError):
    """Raised when ORS is unreachable, errors, or returns an unexpected
    payload. Callers must catch this and degrade gracefully -- distance
    pricing simply falls back to zero, it never blocks intake or quoting."""


def _config() -> tuple[str, str]:
    api_key = os.environ.get("ORS_API_KEY")
    base_url = os.environ.get("ORS_BASE_URL", DEFAULT_BASE_URL)
    if not api_key:
        raise OrsClientError("ORS_API_KEY is not configured")
    return base_url, api_key


def autocomplete(
    query: str, *, size: int = 5, timeout_s: float = DEFAULT_TIMEOUT_S
) -> list[dict]:
    """Address suggestions for `query`: `[{"label": ..., "lat": ..., "lng": ...}, ...]`.

    Raises `OrsClientError` on any transport, HTTP, or parse failure.
    """
    base_url, api_key = _config()
    try:
        response = httpx.get(
            f"{base_url.rstrip('/')}/geocode/autocomplete",
            params={"api_key": api_key, "text": query, "size": size},
            timeout=timeout_s,
        )
        response.raise_for_status()
        body = response.json()
        suggestions = []
        for feature in body["features"]:
            lng, lat = feature["geometry"]["coordinates"]
            suggestions.append(
                {
                    "label": feature["properties"]["label"],
                    "lat": lat,
                    "lng": lng,
                }
            )
        return suggestions
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
        raise OrsClientError(f"ORS autocomplete request failed: {exc}") from exc


def geocode(address: str, *, timeout_s: float = DEFAULT_TIMEOUT_S) -> tuple[float, float] | None:
    """Geocode `address` to `(lat, lng)`, or `None` if no match was found.

    Raises `OrsClientError` on any transport, HTTP, or parse failure.
    """
    base_url, api_key = _config()
    try:
        response = httpx.get(
            f"{base_url.rstrip('/')}/geocode/search",
            params={"api_key": api_key, "text": address, "size": 1},
            timeout=timeout_s,
        )
        response.raise_for_status()
        body = response.json()
        features = body["features"]
        if not features:
            return None
        lng, lat = features[0]["geometry"]["coordinates"]
        return float(lat), float(lng)
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
        raise OrsClientError(f"ORS geocode request failed: {exc}") from exc


def route_distance_km(
    waypoints: list[tuple[float, float]],
    *,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> float:
    """Driving distance in km for the single continuous route visiting each
    `(lat, lng)` in `waypoints`, in order (e.g. depot -> origin ->
    destination -> depot) -- this is the truck's actual driven route, not
    the sum of independent point-to-point legs.

    Raises `OrsClientError` on any transport, HTTP, or parse failure.
    """
    base_url, api_key = _config()
    coordinates = [[lng, lat] for lat, lng in waypoints]
    try:
        response = httpx.post(
            f"{base_url.rstrip('/')}/v2/directions/driving-car",
            json={"coordinates": coordinates},
            headers={"Authorization": api_key},
            timeout=timeout_s,
        )
        response.raise_for_status()
        body = response.json()
        distance_m = body["routes"][0]["summary"]["distance"]
        return float(distance_m) / 1000.0
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
        raise OrsClientError(f"ORS routing request failed: {exc}") from exc
