from __future__ import annotations

import json
import random
import socket
import time
from datetime import datetime, timezone
from enum import Enum, IntEnum
from typing import Any

import ntplib
import requests
from requests.adapters import HTTPAdapter

from .log import get_logger

# Type alias for JSON
JSON = dict[str, Any]

BASE_URL = "https://mobile.southwest.com/api/"
NTP_SERVER = "time.nist.gov"
NTP_BACKUP_SERVER = "time.cloudflare.com"

# Additional NTP servers for better reliability
NTP_TERTIARY_SERVER = "pool.ntp.org"

logger = get_logger(__name__)


def create_session() -> requests.Session:
    """
    Create a requests Session configured for optimal performance.
    Sessions maintain persistent TCP connections via connection pooling,
    avoiding TCP handshake and TLS negotiation overhead on repeated requests.
    """
    session = requests.Session()

    # Configure connection pooling for better performance
    # pool_connections: Number of connection pools to cache
    # pool_maxsize: Maximum number of connections to save in the pool
    adapter = HTTPAdapter(pool_connections=10, pool_maxsize=10)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    return session


def random_sleep_duration(min_duration: float, max_duration: float) -> float:
    return random.uniform(min_duration, max_duration)


def make_request(
    method: str,
    site: str,
    headers: JSON,
    info: JSON,
    max_attempts: int = 20,
    random_sleep: bool = True,
    session: requests.Session | None = None,
) -> JSON:
    """
    Makes a request to the Southwest servers. For increased reliability, the request is performed
    multiple times on failure. This request retrying is also necessary for check-ins, as check-ins
    may start early.

    Args:
        method: HTTP method (GET or POST)
        site: API endpoint path
        headers: Request headers
        info: Request body/params
        max_attempts: Maximum retry attempts
        random_sleep: Whether to use random sleep between retries (False for check-in)
        session: Optional requests.Session for connection reuse (improves performance)
    """
    # Ensure the URL is not malformed
    site = site.replace("//", "/").lstrip("/")
    url = BASE_URL + site

    attempts = 0
    while attempts < max_attempts:
        attempts += 1

        try:
            response = _do_request(method, url, headers, info, session)
            if response.status_code == 200:
                logger.debug("Successfully made request after %d attempts", attempts)
                return response.json()

            response_body = response.content.decode()
            error_msg = f"{response.reason} ({response.status_code})"
        except requests.RequestException as err:
            response_body = ""
            error_msg = str(err)

        error = RequestError(error_msg, response_body)

        try:
            _handle_southwest_error_code(error)
        except (RequestError, AirportCheckInError) as err:
            # Stop requesting after one attempt for special codes, as the requests won't succeed
            error = err
            break

        # Use shorter retry delays for check-in requests (random_sleep=False)
        # to maximize chances of getting the check-in through quickly
        if random_sleep:
            sleep_time = random_sleep_duration(1, 3)
        else:
            # Exponential backoff with very short initial delay for check-in
            # attempts 1-3: 0.05s, 0.1s, 0.2s; then caps at 0.5s
            sleep_time = min(0.05 * (2 ** (attempts - 1)), 0.5)

        logger.debug(
            "Request error on attempt %d: %s. Sleeping for %.2f seconds until next attempt",
            attempts,
            error_msg,
            sleep_time,
        )
        time.sleep(sleep_time)

    logger.debug("Failed to make request after %d attempts: %s", attempts, error_msg)
    logger.debug("Response body: %s", response_body)
    raise error


def _do_request(
    method: str, url: str, headers: JSON, info: JSON, session: requests.Session | None = None
) -> requests.Response:
    """
    Perform the actual HTTP request. Uses session if provided for connection reuse.
    """
    if session is not None:
        if method.upper() == "POST":
            response = session.post(url, headers=headers, json=info)
        else:
            response = session.get(url, headers=headers, params=info)
    else:
        if method.upper() == "POST":
            response = requests.post(url, headers=headers, json=info)
        else:
            response = requests.get(url, headers=headers, params=info)

    return response


class SouthwestErrorCode(IntEnum):
    AIRPORT_CHECKIN_REQUIRED = 400511206
    FLIGHT_IN_PAST = 400520413
    INVALID_CONFIRMATION_NUMBER_LENGTH = 400310456
    PASSENGER_NOT_FOUND = 400620480
    RESERVATION_CANCELLED = 400520414
    RESERVATION_NOT_FOUND = 400620389


def _handle_southwest_error_code(error: RequestError) -> None:
    if error.southwest_code == SouthwestErrorCode.AIRPORT_CHECKIN_REQUIRED:
        raise AirportCheckInError("Airport check-in is required")

    if error.southwest_code == SouthwestErrorCode.FLIGHT_IN_PAST:
        raise RequestError("Flight has already departed")

    if error.southwest_code == SouthwestErrorCode.INVALID_CONFIRMATION_NUMBER_LENGTH:
        raise RequestError("Invalid confirmation number length")

    if error.southwest_code == SouthwestErrorCode.PASSENGER_NOT_FOUND:
        raise RequestError("Passenger not found on reservation")

    if error.southwest_code == SouthwestErrorCode.RESERVATION_NOT_FOUND:
        raise RequestError("Reservation not found")

    if error.southwest_code == SouthwestErrorCode.RESERVATION_CANCELLED:
        raise RequestError("Reservation has been cancelled")


def get_current_time() -> datetime:
    """
    Fetch the current time from an NTP server. Times are sometimes off on computers running the
    script and since check-ins rely on exact times, this ensures check-ins are done at the correct
    time. Falls back to local time if the request to the NTP servers fail.

    Times are returned in UTC.
    """
    c = ntplib.NTPClient()
    ntp_servers = [NTP_SERVER, NTP_BACKUP_SERVER, NTP_TERTIARY_SERVER]

    for server in ntp_servers:
        try:
            # Reduced timeout from 10s to 5s for faster fallback
            response = c.request(server, version=3, timeout=5)
            return datetime.fromtimestamp(response.tx_time, timezone.utc)
        except (socket.gaierror, ntplib.NTPException, OSError):
            logger.debug("Failed to get time from %s, trying next server", server)
            continue

    logger.debug("Error requesting time from all NTP servers. Using local time")
    return datetime.now(timezone.utc)


class RequestError(Exception):
    """A custom exception when a request fails"""

    def __init__(self, message: str, response_body: str = "") -> None:
        super().__init__(message)

        try:
            response_json = json.loads(response_body)
        except json.decoder.JSONDecodeError:
            response_json = {}

        self.southwest_code = response_json.get("code")


class AirportCheckInError(Exception):
    """A custom exception when airport check-in is required"""


class LoginError(Exception):
    """A custom exception when a login fails"""

    def __init__(self, reason: str, status_code: int) -> None:
        super().__init__(f"Reason: {reason}. Status code: {status_code}")
        self.status_code = status_code


class FlightChangeError(Exception):
    """A custom exception for flights that cannot be changed"""


class DriverTimeoutError(Exception):
    """A custom exception for when the webdriver times out waiting for attributes to be set"""


class NotificationLevel(IntEnum):
    NOTICE = 1
    INFO = 2
    CHECKIN = 3
    ERROR = 4


# Switch to StrEnum when Python 3.10 support is dropped
class CheckFaresOption(str, Enum):
    NO = "no"
    SAME_FLIGHT = "same_flight"
    SAME_DAY_NONSTOP = "same_day_nonstop"
    SAME_DAY = "same_day"


def is_truthy(arg: bool | int | str) -> bool:
    """
    Convert "truthy" strings into Booleans.

    Examples:
        >>> is_truthy('yes')
        True

    Args:
        arg: Truthy value (True values are y, yes, t, true, on and 1; false values are n, no,
        f, false, off and 0. Raises ValueError if val is anything else.
    """
    if isinstance(arg, bool):
        return arg

    val = str(arg).lower()
    if val in ("y", "yes", "t", "true", "on", "1"):
        return True
    if val in ("n", "no", "f", "false", "off", "0"):
        return False
    raise ValueError(f"Invalid truthy value: `{arg}`")
