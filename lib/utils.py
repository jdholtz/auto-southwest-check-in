import json
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
NTP_SERVER = "us.pool.ntp.org"
logger = get_logger(__name__)

RESERVATION_NOT_FOUND_CODE = 400620389


def make_request(method: str, site: str, headers: JSON, info: JSON, max_attempts=20) -> JSON:
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
        error = RequestError(None, response_body)

        if error.southwest_code == RESERVATION_NOT_FOUND_CODE:
            # Don't keep requesting if the reservation was not found
            logger.debug("Reservation not found")
            break

        time.sleep(0.5)

    error_msg = response.reason + " " + str(response.status_code)
    logger.debug("Failed to make request after %d attempts: %s", attempts, error_msg)

    logger.debug("Response body: %s", response_body)
    raise RequestError(error_msg, response_body)


def get_current_time() -> datetime:
    """
    Fetch the current time from an NTP server. Times are sometimes off on computers running the
    script and since check-ins rely on exact times, this ensures check-ins are done at the correct
    time. Falls back to local time if the request to the NTP server fails.

    Times are returned in UTC.
    """
    c = ntplib.NTPClient()

    try:
        response = c.request(NTP_SERVER, version=3)
    except (socket.gaierror, ntplib.NTPException):
        logger.debug("Error requesting time from NTP server. Using local time")
        return datetime.now(timezone.utc)

    return datetime.fromtimestamp(response.tx_time, timezone.utc).replace(tzinfo=None)


# Make a custom exception when a request fails
class RequestError(Exception):
    def __init__(self, message: str, response_body: str = "") -> None:
        super().__init__(message)

        try:
            response_json = json.loads(response_body)
        except json.decoder.JSONDecodeError:
            response_json = {}

        self.southwest_code = response_json.get("code")


# Make a custom exception when a login fails
class LoginError(Exception):
    def __init__(self, reason: str, status_code: int) -> None:
        super().__init__(f"Reason: {reason}. Status code: {status_code}")
        self.status_code = status_code


# Make a custom exception for flights that cannot be changed
class FlightChangeError(Exception):
    pass


class NotificationLevel(IntEnum):
    INFO = 1
    ERROR = 2


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
