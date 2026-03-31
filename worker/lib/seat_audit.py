"""Seat upgrade audit system - captures every step of the seat selection process."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from typing import Any

from .log import get_logger

logger = get_logger(__name__)

AUDIT_BASE_DIR = "/app/data/captures"


class SeatUpgradeAudit:
    """Tracks every step of a seat upgrade attempt with timing, screenshots,
    browser console logs, and detailed state capture."""

    def __init__(self, flight_id: str, browser_session: Any, db_conn_factory: Any) -> None:
        self.flight_id = flight_id
        self.browser_session = browser_session
        self.db_conn_factory = db_conn_factory
        self.capture_dir = os.path.join(AUDIT_BASE_DIR, flight_id, f"seat_audit_{int(time.time())}")
        self.steps: list[dict] = []
        self._current_step: dict | None = None
        self._started_at: str | None = None
        self._start_time: float = 0
        self._all_console_logs: list[dict] = []

    def start(self) -> None:
        """Initialize the audit. Call at the beginning of a seat upgrade attempt."""
        os.makedirs(self.capture_dir, exist_ok=True)
        self._started_at = datetime.utcnow().isoformat()
        self._start_time = time.time()
        logger.info("Seat upgrade audit started for flight %s", self.flight_id)

    def begin_step(self, name: str) -> None:
        """Begin tracking a new step. Auto-ends the previous step if still open."""
        if self._current_step:
            self.end_step(success=True, data={"auto_closed": True})

        self._current_step = {
            "name": name,
            "order": len(self.steps) + 1,
            "started_at": datetime.utcnow().isoformat(),
            "_start_time": time.time(),
            "success": None,
            "url": None,
            "page_title": None,
            "cookies": None,
            "screenshot": None,
            "data": {},
            "console_errors": [],
        }

    def end_step(self, success: bool, data: dict | None = None) -> None:
        """End the current step with a success/failure status and optional data."""
        if not self._current_step:
            return

        step = self._current_step
        elapsed = time.time() - step["_start_time"]
        step["duration_ms"] = int(elapsed * 1000)
        step["success"] = success
        if data:
            step["data"] = data

        # Capture browser state
        self._capture_browser_state(step)

        # Capture console logs since last step
        self._capture_console_logs(step)

        # Take screenshot
        screenshot_name = f"{step['order']:02d}_{step['name']}.png"
        self._take_screenshot(screenshot_name)
        step["screenshot"] = screenshot_name

        # Clean up internal fields
        del step["_start_time"]

        self.steps.append(step)
        self._current_step = None

        status = "✓" if success else "✗"
        logger.info(
            "Seat audit step %d [%s] %s (%dms) url=%s",
            step["order"], step["name"], status, step["duration_ms"],
            step.get("url", "?")
        )

    def finish(self, status: str = "success", error_message: str = "") -> None:
        """Finalize the audit and save to database."""
        if self._current_step:
            self.end_step(success=(status == "success"))

        completed_at = datetime.utcnow().isoformat()
        total_ms = int((time.time() - self._start_time) * 1000)

        # Save manifest
        manifest = {
            "flight_id": self.flight_id,
            "started_at": self._started_at,
            "completed_at": completed_at,
            "total_duration_ms": total_ms,
            "status": status,
            "error_message": error_message,
            "steps": self.steps,
            "console_log_count": len(self._all_console_logs),
        }
        self._save_json("manifest.json", manifest)
        self._save_json("console_logs.json", self._all_console_logs)

        # Save to database
        try:
            conn = self.db_conn_factory()
            conn.execute(
                "INSERT INTO seat_upgrade_audit "
                "(flight_id, started_at, completed_at, status, steps_json, "
                "browser_console_json, capture_dir, error_message) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    self.flight_id,
                    self._started_at,
                    completed_at,
                    status,
                    json.dumps(self.steps, default=str),
                    json.dumps(self._all_console_logs[:200], default=str),  # Cap at 200 entries
                    self.capture_dir,
                    error_message,
                ),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error("Failed to save seat audit to DB: %s", e)

        # Also log to worker_logs for Activity page visibility
        from db import add_log, get_connection
        try:
            conn = self.db_conn_factory()
            step_summary = " → ".join(
                f"{s['name']}({'✓' if s['success'] else '✗'})"
                for s in self.steps
            )
            add_log(
                conn,
                f"Seat audit [{status}] {total_ms}ms: {step_summary}",
                "info" if status == "success" else "warning",
                self.flight_id,
            )
            conn.close()
        except Exception:
            pass

        logger.info(
            "Seat upgrade audit finished: %s (%dms, %d steps)",
            status, total_ms, len(self.steps)
        )

    # ── Private helpers ──────────────────────────────────────────

    def _capture_browser_state(self, step: dict) -> None:
        """Capture current browser URL, title, and cookie count."""
        if not self.browser_session or not self.browser_session._driver:
            return
        try:
            driver = self.browser_session._driver
            step["url"] = driver.current_url
            step["page_title"] = driver.execute_script("return document.title || ''")
            step["cookies"] = len(driver.get_cookies())
        except Exception:
            pass

    def _capture_console_logs(self, step: dict) -> None:
        """Capture browser console logs since the last capture."""
        if not self.browser_session or not self.browser_session._driver:
            return
        try:
            logs = self.browser_session._driver.get_log("browser")
            errors = []
            for log_entry in logs:
                entry = {
                    "level": log_entry.get("level", ""),
                    "message": str(log_entry.get("message", ""))[:500],
                    "source": log_entry.get("source", ""),
                    "timestamp": log_entry.get("timestamp", 0),
                }
                self._all_console_logs.append(entry)
                if entry["level"] in ("SEVERE", "ERROR"):
                    errors.append(entry["message"][:200])
            step["console_errors"] = errors
        except Exception:
            pass

    def _take_screenshot(self, filename: str) -> None:
        """Save a screenshot to the capture directory."""
        if not self.browser_session or not self.browser_session._driver:
            return
        try:
            path = os.path.join(self.capture_dir, filename)
            self.browser_session._driver.save_screenshot(path)
        except Exception as e:
            logger.debug("Screenshot failed for %s: %s", filename, e)

    def _save_json(self, filename: str, data: Any) -> None:
        """Save JSON data to the capture directory."""
        try:
            path = os.path.join(self.capture_dir, filename)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.debug("JSON save failed for %s: %s", filename, e)

    def save_dom(self, filename: str) -> None:
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
        except Exception as e:
            logger.debug("DOM save failed for %s: %s", filename, e)
