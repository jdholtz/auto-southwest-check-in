import json
import random
import socket
import time
from datetime import datetime, timezone
from enum import IntEnum
from typing import Any, Dict, Union

import ntplib
import requests

from .log import get_logger

# Type alias for JSON
JSON = Dict[str, Any]

BASE_URL = "https://mobile.southwest.com/api/"
NTP_SERVER = "pool.ntp.org"
NTP_BACKUP_SERVER = "time.cloudflare.com"

AIRPORT_CHECKIN_REQUIRED_CODE = 400511206
INVALID_CONFIRMATION_NUMBER_LENGTH_CODE = 400310456
PASSENGER_NOT_FOUND_CODE = 400620480
RESERVATION_NOT_FOUND_CODE = 400620389

logger = get_logger(__name__)


def random_sleep_duration(min_duration: float, max_duration: float) -> float:
    return random.uniform(min_duration, max_duration)


def _handle_southwest_error_code(error: "RequestError") -> None:
    if error.southwest_code == AIRPORT_CHECKIN_REQUIRED_CODE:
        raise AirportCheckInError("Airport check-in is required")

    if error.southwest_code == INVALID_CONFIRMATION_NUMBER_LENGTH_CODE:
        raise RequestError("Invalid confirmation number length")

    if error.southwest_code == PASSENGER_NOT_FOUND_CODE:
        raise RequestError("Passenger not found on reservation")

    if error.southwest_code == RESERVATION_NOT_FOUND_CODE:
        raise RequestError("Reservation not found")


def make_request(
    method: str, site: str, headers: JSON, info: JSON, max_attempts=20, random_sleep=True
) -> JSON:
    """
    Makes a request to the Southwest servers. For increased reliability, the request is performed
    multiple times on failure. This request retrying is also necessary for check-ins, as check-in
    requests are started five seconds ahead of the actual check-in time (in case the Southwest
    server is not in sync with our NTP server or local computer).
    """
    # Ensure the URL is not malformed
    site = site.replace("//", "/").lstrip("/")
    url = BASE_URL + site

    attempts = 0
    while attempts < max_attempts:
        attempts += 1
        if method == "POST":
            response = requests.post(url, headers=headers, json=info)
        else:
            response = requests.get(url, headers=headers, params=info)

        if response.status_code == 200:
            logger.debug("Successfully made request after %d attempts", attempts)
            return response.json()

        # Request did not succeed
        response_body = response.content.decode()
        error_msg = response.reason + " " + str(response.status_code)
        error = RequestError(error_msg, response_body)

        try:
            _handle_southwest_error_code(error)
        except (RequestError, AirportCheckInError) as err:
            # Stop requesting after one attempt for special codes, as the requests won't succeed
            error = err
            break

        if random_sleep:
            sleep_time = random_sleep_duration(1, 3)
        else:
            sleep_time = 0.5

        logger.debug(
            f"Request error on attempt {attempts}: {error_msg}. Sleeping for {sleep_time:.2f} "
            "seconds until next attempt"
        )
        time.sleep(sleep_time)

    logger.debug("Failed to make request after %d attempts: %s", attempts, error_msg)
    logger.debug("Response body: %s", response_body)
    raise error


def get_current_time() -> datetime:
    """
    Fetch the current time from an NTP server. Times are sometimes off on computers running the
    script and since check-ins rely on exact times, this ensures check-ins are done at the correct
    time. Falls back to local time if the request to the NTP servers fail.

    Times are returned in UTC.
    """
    c = ntplib.NTPClient()

    try:
        # Set a longer timeout to make the request more reliable
        response = c.request(NTP_SERVER, version=3, timeout=10)
    except (socket.gaierror, ntplib.NTPException):
        try:
            # Try the backup NTP server before falling back to local time. Increases reliability of
            # fetching the time significantly
            response = c.request(NTP_BACKUP_SERVER, version=3, timeout=10)
        except (socket.gaierror, ntplib.NTPException):
            logger.debug("Error requesting time from NTP servers. Using local time")
            return datetime.now(timezone.utc).replace(tzinfo=None)

    return datetime.fromtimestamp(response.tx_time, timezone.utc).replace(tzinfo=None)


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
    ERROR = 3


def is_truthy(arg: Union[bool, int, str]) -> bool:
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
