"""Check-in data capture engine for learning Southwest's API behavior.

Captures screenshots, full API request/response bodies, network traffic,
and DOM snapshots during the check-in process. All heavy I/O happens AFTER
the time-critical check-in POST requests complete.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from typing import Any

from .log import get_logger

logger = get_logger(__name__)

CAPTURES_DIR = "/app/data/captures"
MAX_RESPONSE_BODY_SIZE = 50000  # 50KB per network response body


class CheckInCapture:
    """Captures technical data during check-in for learning/debugging."""

    def __init__(self, flight_id: str, browser_session: Any, db_conn_factory: Any) -> None:
        self.flight_id = flight_id
        self.browser_session = browser_session
        self.db_conn_factory = db_conn_factory
        self.capture_dir = os.path.join(CAPTURES_DIR, flight_id)
        self.manifest: dict = {
            "flight_id": flight_id,
            "files": [],
            "started_at": None,
            "finished_at": None,
            "checkin_success": None,
            "errors": [],
        }
        self.network_log: list[dict] = []
        self._capturing_network = False

    def start_capture(self) -> None:
        """Called BEFORE check-in. Takes pre-screenshot, starts network recording."""
        try:
            os.makedirs(self.capture_dir, exist_ok=True)
            self.manifest["started_at"] = datetime.utcnow().isoformat()
            logger.info("Starting check-in capture for flight %s", self.flight_id)

            self._take_screenshot("01_pre_checkin.png")
            self._start_network_recording()
        except Exception as e:
            logger.error("Error starting capture: %s", e)
            self.manifest["errors"].append(f"start_capture: {e}")

    def record_api_call(
        self,
        step_name: str,
        method: str,
        url: str,
        request_body: Any,
        status: int,
        response_body: Any,
    ) -> None:
        """Called DURING check-in to store full request/response in memory.
        Actual disk write happens in finish_capture()."""
        try:
            self._save_json(f"{step_name}_request.json", {
                "method": method,
                "url": url,
                "body": request_body,
                "timestamp": datetime.utcnow().isoformat(),
            })
            self._save_json(f"{step_name}_response.json", {
                "status": status,
                "body": response_body,
                "timestamp": datetime.utcnow().isoformat(),
            })
        except Exception as e:
            logger.error("Error recording API call %s: %s", step_name, e)
            self.manifest["errors"].append(f"record_api_call({step_name}): {e}")

    def finish_capture(self, success: bool = True) -> None:
        """Called AFTER check-in completes. Takes post-screenshots, harvests
        network traffic, saves DOM, writes manifest. This is where the heavy
        I/O happens (non-time-critical)."""
        self.manifest["checkin_success"] = success
        try:
            self._take_screenshot("04_post_checkin.png")
            self._save_dom("05_post_checkin_dom.html")
            self._harvest_network_bodies()
            self._save_json("network_log.json", self.network_log)

            self.manifest["finished_at"] = datetime.utcnow().isoformat()
            self.manifest["network_requests_captured"] = len(self.network_log)
            self._save_json("manifest.json", self.manifest)

            self._record_in_db()
            logger.info(
                "Check-in capture complete for flight %s: %d files, %d network events",
                self.flight_id,
                len(self.manifest["files"]),
                len(self.network_log),
            )
        except Exception as e:
            logger.error("Error finishing capture: %s", e)
            self.manifest["errors"].append(f"finish_capture: {e}")
            # Still try to save manifest even if something failed
            try:
                self._save_json("manifest.json", self.manifest)
            except Exception:
                pass

    def capture_page(self, name: str) -> None:
        """Capture a screenshot and DOM of the current page (e.g., seat selection)."""
        try:
            self._take_screenshot(f"{name}.png")
            self._save_dom(f"{name}_dom.html")
        except Exception as e:
            logger.error("Error capturing page %s: %s", name, e)
            self.manifest["errors"].append(f"capture_page({name}): {e}")

    # ── Private helpers ──────────────────────────────────────────────

    def _take_screenshot(self, filename: str) -> None:
        """Save a screenshot of the current browser state."""
        if not self.browser_session or not self.browser_session._driver:
            self.manifest["errors"].append(f"screenshot({filename}): no browser driver")
            return
        try:
            path = os.path.join(self.capture_dir, filename)
            self.browser_session._driver.save_screenshot(path)
            size = os.path.getsize(path)
            self.manifest["files"].append({
                "name": filename,
                "type": "screenshot",
                "size_bytes": size,
                "captured_at": datetime.utcnow().isoformat(),
            })
            logger.debug("Screenshot saved: %s (%d bytes)", filename, size)
        except Exception as e:
            logger.error("Screenshot failed for %s: %s", filename, e)
            self.manifest["errors"].append(f"screenshot({filename}): {e}")

    def _save_dom(self, filename: str) -> None:
        """Save the current page DOM as HTML."""
        if not self.browser_session or not self.browser_session._driver:
            return
        try:
            html = self.browser_session._driver.execute_script(
                "return document.documentElement.outerHTML"
            )
            path = os.path.join(self.capture_dir, filename)
            with open(path, "w", encoding="utf-8") as f:
                f.write(html)
            size = os.path.getsize(path)
            self.manifest["files"].append({
                "name": filename,
                "type": "dom",
                "size_bytes": size,
                "captured_at": datetime.utcnow().isoformat(),
            })
            logger.debug("DOM saved: %s (%d bytes)", filename, size)
        except Exception as e:
            logger.error("DOM save failed for %s: %s", filename, e)
            self.manifest["errors"].append(f"dom({filename}): {e}")

    def _save_json(self, filename: str, data: Any) -> None:
        """Save a JSON file to the capture directory."""
        try:
            path = os.path.join(self.capture_dir, filename)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
            size = os.path.getsize(path)
            # Only add to manifest if not already tracked (manifest.json is self-referential)
            if filename != "manifest.json":
                self.manifest["files"].append({
                    "name": filename,
                    "type": "json",
                    "size_bytes": size,
                    "captured_at": datetime.utcnow().isoformat(),
                })
        except Exception as e:
            logger.error("JSON save failed for %s: %s", filename, e)
            self.manifest["errors"].append(f"json({filename}): {e}")

    def _start_network_recording(self) -> None:
        """Register CDP listeners to capture ALL network traffic."""
        if not self.browser_session or not self.browser_session._driver:
            return

        def on_request(data: dict) -> None:
            try:
                params = data.get("params", {})
                request = params.get("request", {})
                self.network_log.append({
                    "type": "request",
                    "timestamp": datetime.utcnow().isoformat(),
                    "requestId": params.get("requestId"),
                    "url": request.get("url", ""),
                    "method": request.get("method", ""),
                    "headers": request.get("headers", {}),
                    "postData": request.get("postData", ""),
                })
            except Exception:
                pass

        def on_response(data: dict) -> None:
            try:
                params = data.get("params", {})
                response = params.get("response", {})
                self.network_log.append({
                    "type": "response",
                    "timestamp": datetime.utcnow().isoformat(),
                    "requestId": params.get("requestId"),
                    "url": response.get("url", ""),
                    "status": response.get("status", 0),
                    "statusText": response.get("statusText", ""),
                    "headers": response.get("headers", {}),
                    "mimeType": response.get("mimeType", ""),
                })
            except Exception:
                pass

        try:
            self.browser_session._driver.add_cdp_listener(
                "Network.requestWillBeSent", on_request
            )
            self.browser_session._driver.add_cdp_listener(
                "Network.responseReceived", on_response
            )
            self._capturing_network = True
            logger.debug("Network recording started")
        except Exception as e:
            logger.error("Failed to start network recording: %s", e)
            self.manifest["errors"].append(f"network_recording: {e}")

    def _harvest_network_bodies(self) -> None:
        """After check-in, retrieve response bodies for captured network responses.
        This is NON-TIME-CRITICAL and runs after check-in completes."""
        if not self.browser_session or not self.browser_session._driver:
            return

        harvested = 0
        failed = 0
        for entry in self.network_log:
            if entry.get("type") != "response" or not entry.get("requestId"):
                continue
            try:
                body_response = self.browser_session._driver.execute_cdp_cmd(
                    "Network.getResponseBody",
                    {"requestId": entry["requestId"]},
                )
                body = body_response.get("body", "")
                entry["response_body"] = body[:MAX_RESPONSE_BODY_SIZE]
                entry["body_truncated"] = len(body) > MAX_RESPONSE_BODY_SIZE
                entry["body_base64_encoded"] = body_response.get("base64Encoded", False)
                harvested += 1
            except Exception:
                entry["response_body"] = "(unavailable - evicted from browser memory)"
                entry["body_truncated"] = False
                failed += 1

        logger.debug(
            "Network body harvest: %d retrieved, %d unavailable", harvested, failed
        )

    def _record_in_db(self) -> None:
        """Save capture metadata to the database."""
        try:
            from db import get_connection

            conn = self.db_conn_factory()
            total_size = sum(
                f.get("size_bytes", 0) for f in self.manifest.get("files", [])
            )
            conn.execute(
                "INSERT INTO checkin_captures (flight_id, capture_dir, manifest_json, "
                "file_count, total_size_bytes) VALUES (?, ?, ?, ?, ?)",
                (
                    self.flight_id,
                    self.capture_dir,
                    json.dumps(self.manifest, default=str),
                    len(self.manifest.get("files", [])),
                    total_size,
                ),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error("Failed to record capture in DB: %s", e)
