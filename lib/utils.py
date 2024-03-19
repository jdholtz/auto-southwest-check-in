import json
import time
from enum import IntEnum
from typing import Any, Dict, Union

import requests

from .log import get_logger

# Type alias for JSON
JSON = Dict[str, Any]

BASE_URL = "https://mobile.southwest.com/api/"
logger = get_logger(__name__)


def make_request(method: str, site: str, headers: JSON, info: JSON, max_attempts=20) -> JSON:
    # Ensure the URL is not malformed
    site = site.replace("//", "/").lstrip("/")

    url = BASE_URL + site

    # In the case that your server and the Southwest server aren't in sync,
    # this requests multiple times for a better chance at success when checking in
    attempts = 1
    while attempts <= max_attempts:
        if method == "POST":
            response = requests.post(url, headers=headers, json=info)
        else:
            response = requests.get(url, headers=headers, params=info)

        if response.status_code == 200:
            logger.debug("Successfully made request after %d attempts", attempts)
            return response.json()

        attempts += 1
        time.sleep(0.5)

    error_msg = response.reason + " " + str(response.status_code)
    logger.debug("Failed to make request after %d attempts: %s", max_attempts, error_msg)

    response_body = response.content.decode()
    logger.debug("Response body: %s", response_body)
    raise RequestError(error_msg, response_body)


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
