"""Persistent browser session that routes API calls through the browser to bypass WAF."""

from __future__ import annotations

import json
import re
import time
import threading
from typing import Any
from urllib.parse import urlencode

from sbvirtualdisplay import Display
from seleniumbase import Driver
from seleniumbase.fixtures import page_actions as seleniumbase_actions

from .config import IS_DOCKER
from .log import get_logger
from .utils import DriverTimeoutError, LoginError, RequestError, random_sleep_duration

JSON = dict[str, Any]

BASE_URL = "https://mobile.southwest.com"
MOBILE_LOGIN_URL = BASE_URL + "/login?webView=true"
MOBILE_HEADERS_URL = (
    BASE_URL + "/api/mobile-air-booking/v1/mobile-air-booking/feature/shopping-details"
)
API_BASE_URL = BASE_URL + "/api/"

ACCOUNT_URL = "https://www.southwest.com/loyalty/myaccount"
SUCCESSFUL_LOGIN_URL = "https://www.southwest.com/api/security/v4/security/token"
TRIPS_URL = (
    "https://www.southwest.com/api/loyalty-management/v2/loyalty-management/"
    "accounts/self/future-air-reservations-secure"
)

INVALID_CREDENTIALS_CODE = 400518024
WAIT_TIMEOUT_SECS = 180
SESSION_MAX_AGE = 25 * 60  # 25 minutes before forced restart

logger = get_logger(__name__)

FETCH_SCRIPT = """
var callback = arguments[arguments.length - 1];
var method = arguments[0];
var url = arguments[1];
var headersStr = arguments[2];
var body = arguments[3];

try {
    var headersObj = JSON.parse(headersStr);
    var opts = {
        method: method,
        headers: headersObj,
        credentials: 'include'
    };
    if (body && body !== 'null' && method !== 'GET') {
        opts.body = body;
        if (!headersObj['Content-Type']) {
            opts.headers['Content-Type'] = 'application/json';
        }
    }
    fetch(url, opts)
        .then(function(response) {
            return response.text().then(function(text) {
                callback(JSON.stringify({status: response.status, body: text}));
            });
        })
        .catch(function(err) {
            callback(JSON.stringify({status: 0, body: 'fetch error: ' + err.toString()}));
        });
} catch(e) {
    callback(JSON.stringify({status: 0, body: 'script error: ' + e.toString()}));
}
"""


class BrowserSession:
    """Manages a persistent browser session for routing API requests through the WAF."""

    def __init__(self):
        self._driver: Driver | None = None
        self._display: Display | None = None
        self._lock = threading.Lock()
        self.headers: dict = {}
        self._headers_set = False
        self._started_at: float = 0
        self._login_request_id = None
        self._login_status_code = None
        self._trips_request_id = None

    def start(self) -> None:
        """Start the browser and navigate to mobile site to establish WAF session."""
        with self._lock:
            self._start_internal()

    def _start_internal(self) -> None:
        """Internal start without lock (caller must hold lock)."""
        if self._driver:
            self._stop_internal()

        logger.info("Starting browser session")
        if IS_DOCKER:
            self._start_display()

        driver_version = "keep" if IS_DOCKER else "mlatest"
        self._driver = Driver(
            binary_location=None,
            driver_version=driver_version,
            headed=IS_DOCKER,
            headless1=not IS_DOCKER,
            uc_cdp_events=True,
            undetectable=True,
            incognito=True,
        )
        self._driver.set_script_timeout(60)
        logger.info("Browser version: %s", self._driver.caps.get("browserVersion", "unknown"))

        # Add header capture listener
        self._headers_set = False
        self._driver.add_cdp_listener("Network.requestWillBeSent", self._headers_listener)

        # Navigate to mobile site to pass WAF and capture headers
        logger.info("Loading mobile Southwest site to establish session")
        self._driver.get(MOBILE_LOGIN_URL)
        self._wait_for_headers()

        self._started_at = time.time()
        logger.info("Browser session established with %d headers", len(self.headers))

    def stop(self) -> None:
        """Quit browser and stop display."""
        with self._lock:
            self._stop_internal()

    def _stop_internal(self) -> None:
        """Internal stop without lock."""
        if self._driver:
            try:
                self._driver.quit()
            except Exception:
                pass
            self._driver = None
        if self._display:
            try:
                self._display.stop()
            except Exception:
                pass
            self._display = None
        self._headers_set = False
        logger.info("Browser session stopped")

    def ensure_alive(self) -> None:
        """Restart browser if crashed or session is stale."""
        with self._lock:
            needs_restart = False

            if not self._driver:
                needs_restart = True
            elif time.time() - self._started_at > SESSION_MAX_AGE:
                logger.info("Session expired (age > %d seconds), restarting", SESSION_MAX_AGE)
                needs_restart = True
            else:
                try:
                    self._driver.execute_script("return 1")
                except Exception:
                    logger.warning("Browser health check failed, restarting")
                    needs_restart = True

            if needs_restart:
                self._start_internal()

    def execute_fetch(self, method: str, url: str, headers: dict, body: str | None) -> tuple[int, str]:
        """Run fetch() in the browser and return (status_code, response_body).
        Caller must hold the lock."""
        if not self._driver:
            raise DriverTimeoutError("Browser session not started")

        headers_json = json.dumps(headers)
        body_json = json.dumps(body) if body and method.upper() != "GET" else "null"
        if method.upper() != "GET" and body:
            body_json = body if isinstance(body, str) else json.dumps(body)

        try:
            result_str = self._driver.execute_async_script(
                FETCH_SCRIPT, method.upper(), url, headers_json, body_json
            )
            result = json.loads(result_str)
            return result["status"], result["body"]
        except Exception as e:
            logger.error("execute_fetch error: %s", e)
            raise

    def make_request(
        self,
        method: str,
        site: str,
        headers: dict,
        info: dict | None,
        max_attempts: int = 20,
        random_sleep: bool = True,
    ) -> dict:
        """Make an API request through the browser, with retry logic."""
        # Build full URL
        site = site.replace("//", "/").lstrip("/")
        url = API_BASE_URL + site

        if method.upper() == "GET" and info:
            url = url + "?" + urlencode(info)
            body = None
        else:
            body = json.dumps(info) if info else None

        # Merge captured session headers with passed headers
        merged_headers = {**self.headers, **headers} if headers else dict(self.headers)

        attempts = 0
        error_msg = ""
        response_body = ""

        while attempts < max_attempts:
            attempts += 1
            try:
                with self._lock:
                    status, response_body = self.execute_fetch(method, url, merged_headers, body)

                if status == 200:
                    logger.debug("Browser fetch succeeded after %d attempts", attempts)
                    return json.loads(response_body)

                error_msg = f"{status}"
                if status == 403:
                    error_msg = f"Forbidden ({status})"
                    # WAF session may be stale, restart on next attempt
                    if attempts < max_attempts:
                        logger.warning("Got 403, restarting browser session for retry")
                        with self._lock:
                            self._start_internal()
                        merged_headers = {**self.headers, **headers} if headers else dict(self.headers)

            except Exception as e:
                error_msg = str(e)
                response_body = ""

            # Handle Southwest error codes
            error = RequestError(error_msg, response_body)
            try:
                from .utils import _handle_southwest_error_code, AirportCheckInError
                _handle_southwest_error_code(error)
            except (RequestError, AirportCheckInError) as err:
                raise err

            sleep_time = random_sleep_duration(1, 3) if random_sleep else 0.5
            logger.debug("Browser fetch attempt %d failed: %s. Sleeping %.1fs", attempts, error_msg, sleep_time)
            time.sleep(sleep_time)

        raise RequestError(error_msg, response_body)

    def login_and_get_reservations(self, username: str, password: str) -> tuple[list[dict], str, str]:
        """Log into a Southwest account and return (reservations, first_name, last_name).

        After login, navigates back to mobile site to maintain API session.
        """
        with self._lock:
            if not self._driver:
                self._start_internal()

            # Reset login state
            self._login_request_id = None
            self._login_status_code = None
            self._trips_request_id = None

            self._driver.add_cdp_listener("Network.responseReceived", self._login_listener)

            # Navigate to login page
            logger.info("Loading Southwest login page for account login")
            self._driver.get(ACCOUNT_URL)

            # Enter credentials
            time.sleep(random_sleep_duration(1, 3))
            self._driver.type('input[id="username"]', username)
            self._driver.type('input[id="password"]', f"{password}\n")

            # Wait for login response
            self._wait_for_attribute("_login_request_id")
            login_response = self._get_response_body(self._login_request_id)

            if self._login_status_code != 200:
                error = self._handle_login_error(login_response)
                raise error

            # Extract name
            first_name = (
                login_response.get("customers.userInformation.preferredName")
                or login_response.get("customers.userInformation.firstName", "")
            )
            last_name = login_response.get("customers.userInformation.lastName", "")

            # Wait for reservations
            self._wait_for_attribute("_trips_request_id")
            trips_response = self._get_response_body(self._trips_request_id)
            reservations = trips_response.get("data", [])

            # Navigate back to mobile site to re-establish API session
            logger.info("Navigating back to mobile site after login")
            self._headers_set = False
            self._driver.get(MOBILE_LOGIN_URL)
            self._wait_for_headers()

            self._started_at = time.time()
            logger.info("Session re-established after login with %d headers", len(self.headers))

            return reservations, first_name, last_name

    def _headers_listener(self, data: JSON) -> None:
        request = data["params"]["request"]
        if request["url"] == MOBILE_HEADERS_URL:
            self.headers = self._get_needed_headers(request["headers"])
            self._headers_set = True

    def _login_listener(self, data: JSON) -> None:
        response = data["params"]["response"]
        if response["url"] == SUCCESSFUL_LOGIN_URL:
            self._login_request_id = data["params"]["requestId"]
            self._login_status_code = response["status"]
        elif response["url"] == TRIPS_URL:
            self._trips_request_id = data["params"]["requestId"]

    def _wait_for_headers(self) -> None:
        self._wait_for_attribute("_headers_set", timeout=WAIT_TIMEOUT_SECS)

    def _wait_for_attribute(self, attr: str, timeout: int = WAIT_TIMEOUT_SECS) -> None:
        poll_interval = 0.5
        attempts = 0
        max_attempts = timeout / poll_interval
        while not getattr(self, attr) and attempts < max_attempts:
            time.sleep(poll_interval)
            attempts += 1
        if attempts >= max_attempts:
            raise DriverTimeoutError(f"Timeout waiting for '{attr}'")

    def _get_response_body(self, request_id: str) -> dict:
        response = self._driver.execute_cdp_cmd("Network.getResponseBody", {"requestId": request_id})
        return json.loads(response["body"])

    def _get_needed_headers(self, request_headers: dict) -> dict:
        headers = {}
        for header in request_headers:
            if re.match(r"x-api-key|x-channel-id|user-agent|^[\w-]+?-\w$", header, re.IGNORECASE):
                headers[header] = request_headers[header]
        return headers

    def _handle_login_error(self, response: dict) -> LoginError:
        if response.get("code") == INVALID_CREDENTIALS_CODE:
            reason = "Invalid credentials"
        else:
            reason = "Unknown"
        return LoginError(reason, self._login_status_code)

    def _start_display(self) -> None:
        try:
            self._display = Display(size=(1440, 1880), backend="xvfb")
            self._display.start()
        except Exception as e:
            logger.debug("Failed to start display: %s", e)

    def _click_login_button(self) -> None:
        if self._driver.is_element_visible("div[class^='errorMessage']"):
            return
        login_button = "button#submit"
        try:
            seleniumbase_actions.wait_for_element_not_visible(self._driver, login_button, timeout=5)
        except Exception:
            self._driver.click(login_button)
