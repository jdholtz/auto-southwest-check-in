import logging
import time
from enum import IntEnum
from typing import Any, Dict

import requests

BASE_URL = "https://mobile.southwest.com/api/"
logger = logging.getLogger(__name__)


def make_request(
    method: str, site: str, headers: Dict[str, Any], info: Dict[str, str]
) -> Dict[str, Any]:
    url = BASE_URL + site

    # In the case that your server and the Southwest server aren't in sync,
    # this requests multiple times for a better chance at success when checking in
    attempts = 0
    while attempts < 20:
        if method == "POST":
            response = requests.post(url, headers=headers, json=info)
        else:
            response = requests.get(url, headers=headers, params=info)

        if response.status_code == 200:
            logger.debug("Successfully made request after %d attempts", attempts)
            return response.json()

        attempts += 1
        time.sleep(0.5)

    error = response.reason + " " + str(response.status_code)
    logger.debug("Failed to make request: %s", error)
    raise CheckInError(error)


# Make a custom exception when a check-in fails
class CheckInError(Exception):
    pass


# Make a custom exception when a login fails
class LoginError(Exception):
    pass


class NotificationLevel(IntEnum):
    INFO = 1
    ERROR = 2
