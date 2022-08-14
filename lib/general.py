from enum import IntEnum
import time
from typing import Any, Dict

import requests

BASE_URL = "https://mobile.southwest.com/api/"


def make_request(
    method: str, site: str, headers: Dict[str, str], info: Dict[str, str]
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
            return response.json()

        attempts += 1
        time.sleep(0.5)

    raise CheckInError(response.reason + " " + str(response.status_code))


# Make a custom exception when a check-in fails
class CheckInError(Exception):
    pass


class NotificationLevel(IntEnum):
    INFO = 1
    ERROR = 2
