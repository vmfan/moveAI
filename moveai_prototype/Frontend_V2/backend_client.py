from __future__ import annotations

import os
from typing import Any

import requests


class BackendError(RuntimeError):
    def __init__(self, message: str, detail: Any = None):
        super().__init__(message)
        self.detail = detail


class MoveAIBackend:
    def __init__(self, base_url: str | None = None, timeout: float = 1800.0):
        self.base_url = (base_url or os.getenv("MOVEAI_API_BASE", "http://localhost:8010")).rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = self.session.request(method, self._url(path), timeout=self.timeout, **kwargs)
        except requests.RequestException as exc:
            raise BackendError(
                f"Cannot reach MoveAI backend at {self.base_url} for {method} {path}. "
                f"Start FastAPI first and verify MOVEAI_API_BASE. Details: {exc}"
            ) from exc
        if not response.ok:
            try:
                payload = response.json()
            except ValueError:
                payload = response.text
            detail = payload.get("detail") if isinstance(payload, dict) else payload
            raise BackendError(
                f"Backend returned HTTP {response.status_code} for {method} {path}: {payload}",
                detail=detail,
            )
        if response.status_code == 204 or not response.content:
            return None
        return response.json() if "json" in response.headers.get("content-type", "") else response.content

    @staticmethod
    def extract_job_id(payload: Any) -> int:
        if isinstance(payload, dict) and "id" in payload:
            return int(payload["id"])
        raise BackendError(f"Could not identify job id in backend response: {payload!r}")

    # --- Jobs -----------------------------------------------------------

    def create_job(self) -> tuple[int, Any]:
        payload = self.request("POST", "/api/jobs", json={})
        return self.extract_job_id(payload), payload

    def get_job(self, job_id: int) -> Any:
        return self.request("GET", f"/api/jobs/{job_id}")

    # --- Intake -----------------------------------------------------------

    def submit_intake(self, job_id: int, payload: dict[str, Any]) -> Any:
        return self.request("PUT", f"/api/jobs/{job_id}/intake", json=payload)

    def get_intake(self, job_id: int) -> Any:
        return self.request("GET", f"/api/jobs/{job_id}/intake")

    # --- Inventory --------------------------------------------------------

    def get_inventory(self, job_id: int) -> Any:
        return self.request("GET", f"/api/jobs/{job_id}/inventory")

    def add_declared_item(self, job_id: int, payload: dict[str, Any]) -> Any:
        return self.request("POST", f"/api/jobs/{job_id}/inventory/declared", json=payload)

    def confirm_item(self, job_id: int, item_id: int) -> Any:
        return self.request("POST", f"/api/jobs/{job_id}/inventory/{item_id}/confirm")

    def correct_item(self, job_id: int, item_id: int, width_m: float, height_m: float, depth_m: float) -> Any:
        return self.request(
            "POST",
            f"/api/jobs/{job_id}/inventory/{item_id}/correct",
            json={"width_m": width_m, "height_m": height_m, "depth_m": depth_m},
        )

    def delete_inventory_item(self, job_id: int, item_id: int) -> Any:
        return self.request("DELETE", f"/api/jobs/{job_id}/inventory/{item_id}")

    # --- Geocode --------------------------------------------------------------

    def autocomplete_address(self, query: str) -> list[dict]:
        """Address suggestions `[{"label", "lat", "lng"}, ...]`. Returns `[]`
        on any backend error so a flaky network never blocks typing.
        """
        try:
            result = self.request("GET", "/api/geocode/autocomplete", params={"q": query})
        except BackendError:
            return []
        return result if isinstance(result, list) else []

    # --- Quote --------------------------------------------------------------

    def get_quote(self, job_id: int) -> Any:
        return self.request("GET", f"/api/jobs/{job_id}/quote")

    def regenerate_quote(self, job_id: int) -> Any:
        return self.request("POST", f"/api/jobs/{job_id}/quote/regenerate")

    # --- Booking --------------------------------------------------------------

    def get_booking(self, job_id: int) -> Any:
        return self.request("GET", f"/api/jobs/{job_id}/booking")

    def submit_booking(self, job_id: int, customer_note: str | None = None) -> Any:
        return self.request("POST", f"/api/jobs/{job_id}/booking/submit", json={"customer_note": customer_note})

    def resubmit_booking(self, job_id: int, customer_note: str | None = None) -> Any:
        return self.request("POST", f"/api/jobs/{job_id}/booking/resubmit", json={"customer_note": customer_note})

    # --- Console (staff) --------------------------------------------------------

    def list_console_jobs(self, status: str | None = None) -> Any:
        params = {"status": status} if status else None
        return self.request("GET", "/api/console/bookings", params=params)

    def staff_decision(self, booking_id: int, status: str, staff_note: str | None = None) -> Any:
        return self.request(
            "POST",
            f"/api/console/bookings/{booking_id}/decision",
            json={"status": status, "staff_note": staff_note},
        )

    # --- Capture (AI pipeline) --------------------------------------------------------

    def upload_images(self, job_id: int, uploaded_files: list[Any]) -> Any:
        files = [("files", (f.name, f.getvalue(), f.type or "application/octet-stream")) for f in uploaded_files]
        return self.request("POST", f"/api/jobs/{job_id}/capture/uploads", files=files)

    @staticmethod
    def extract_image_names(payload: Any) -> list[str]:
        """
        Extract the server-generated image names from the upload endpoint's
        documented response shape: {"images": [{"name": ..., "url": ...}, ...]}
        """
        if not isinstance(payload, dict) or not isinstance(payload.get("images"), list):
            raise BackendError(
                f"Unexpected upload response. Expected {{'images': [{{'name': ...}}]}}, received: {payload!r}"
            )
        names = [item["name"] for item in payload["images"] if isinstance(item, dict) and "name" in item]
        if not names:
            raise BackendError(
                "The upload succeeded, but the backend response did not contain any image names. "
                f"Actual response: {payload!r}"
            )
        return names

    def capture(self, job_id: int, image_names: list[str], room_label: str | None = None) -> Any:
        return self.request(
            "POST",
            f"/api/jobs/{job_id}/capture",
            json={"image_names": image_names, "room_label": room_label},
        )

    def get_capture_images(self, job_id: int) -> Any:
        return self.request("GET", f"/api/jobs/{job_id}/capture/images")

    def capture_overlay_url(self, job_id: int, image_name: str) -> str:
        return self._url(f"/api/jobs/{job_id}/capture/overlay.png?image_name={image_name}")

    def capture_depth_url(self, job_id: int, image_name: str) -> str:
        return self._url(f"/api/jobs/{job_id}/capture/depth.png?image_name={image_name}")

    # --- Samples --------------------------------------------------------

    def list_samples(self) -> Any:
        return self.request("GET", "/api/samples")
