from __future__ import annotations

import json
import os
import re
import sys
import time
from typing import TYPE_CHECKING, Any, Dict, List

from seleniumbase import Driver
from seleniumbase.fixtures import page_actions as seleniumbase_actions

from .log import LOGS_DIRECTORY, get_logger
from .utils import LoginError

if TYPE_CHECKING:
    from .checkin_scheduler import CheckInScheduler
    from .reservation_monitor import AccountMonitor

BASE_URL = "https://mobile.southwest.com"
LOGIN_URL = BASE_URL + "/api/security/v4/security/token"
TRIPS_URL = BASE_URL + "/api/mobile-misc/v1/mobile-misc/page/upcoming-trips"
CHECKIN_URL = BASE_URL + "/check-in"
HEADERS_URLS = [
    BASE_URL + "/api/chase/v2/chase/offers",
    BASE_URL + "/api/security/v4/security/userinfo",
]

# Southwest's code when logging in with the incorrect information
INVALID_CREDENTIALS_CODE = 400518024

JSON = Dict[str, Any]

logger = get_logger(__name__)


class WebDriver:
    """
    Controls fetching valid headers for use with the Southwest API.

    This class can be instantiated in two ways:
    1. Setting/refreshing headers before a check-in to ensure the headers are valid. The
    check-in URL is requested in the browser. One of the requests from this initial request
    contains valid headers which are then set for the CheckIn Scheduler.

    2. Logging into an account. In this case, the headers are refreshed and a list of scheduled
    flights are retrieved.

    Some of this code is based off of:
    https://github.com/byalextran/southwest-headers/commit/d2969306edb0976290bfa256d41badcc9698f6ed
    """

    def __init__(self, checkin_scheduler: CheckInScheduler) -> None:
        self.checkin_scheduler = checkin_scheduler
        self.headers_set = False
        self.debug_screenshots = self._should_take_screenshots()

        # For account login
        self.login_request_id = None
        self.login_status_code = None
        self.trips_request_id = None

    def _should_take_screenshots(self) -> bool:
        """
        Determines if the webdriver should take screenshots for debugging based on the CLI arguments
        of the script. Similarly to setting verbose logs, this cannot be kept track of easily in a
        global variable due to the script's use of multiprocessing.
        """
        arguments = sys.argv[1:]
        if "--debug-screenshots" in arguments:
            logger.debug("Taking debug screenshots")
            return True

        return False

    def _take_debug_screenshot(self, driver: Driver, name: str) -> None:
        """Take a screenshot of the browser and save the image as 'name' in LOGS_DIRECTORY"""
        if self.debug_screenshots:
            driver.save_screenshot(os.path.join(LOGS_DIRECTORY, name))

    def set_headers(self) -> None:
        """
        The check-in URL is requested. Since another request contains valid headers
        during the initial request, those headers are set in the CheckIn Scheduler.
        """
        driver = self._get_driver()
        self._take_debug_screenshot(driver, "pre_headers.png")
        logger.debug("Waiting for valid headers")
        # Once this attribute is set, the headers have been set in the checkin_scheduler
        self._wait_for_attribute("headers_set")
        self._take_debug_screenshot(driver, "post_headers.png")

        driver.quit()

    def get_reservations(self, account_monitor: AccountMonitor) -> List[JSON]:
        """
        Logs into the account being monitored to retrieve a list of reservations. Since
        valid headers are produced, they are also grabbed and updated in the check-in scheduler.
        Last, if the account name is not set, it will be set based on the response information.
        """
        driver = self._get_driver()
        driver.add_cdp_listener("Network.responseReceived", self._login_listener)

        logger.debug("Logging into account to get a list of reservations and valid headers")

        # Log in to retrieve the account's reservations and needed headers for later requests
        seleniumbase_actions.wait_for_element_not_visible(driver, ".dimmer")
        self._take_debug_screenshot(driver, "pre_login.png")

        # If a popup came up with an error, click "OK" to remove it.
        # See https://github.com/jdholtz/auto-southwest-check-in/issues/226
        driver.click_if_visible(".button-popup.confirm-button")

        driver.click(".login-button--box")
        driver.type('input[name="userNameOrAccountNumber"]', account_monitor.username)

        # Use quote_plus to workaround a x-www-form-urlencoded encoding bug on the mobile site
        driver.type('input[name="password"]', f"{account_monitor.password}\n")

        # Wait for the necessary information to be set
        self._wait_for_attribute("headers_set")
        self._wait_for_login(driver, account_monitor)
        self._take_debug_screenshot(driver, "post_login.png")

        # The upcoming trips page is also loaded when we log in, so we might as well grab it
        # instead of requesting again later
        reservations = self._fetch_reservations(driver)

        driver.quit()
        return reservations

    def _get_driver(self) -> Driver:
        logger.debug("Starting webdriver for current session")
        browser_path = self.checkin_scheduler.reservation_monitor.config.browser_path

        driver_version = "mlatest"
        if os.environ.get("AUTO_SOUTHWEST_CHECK_IN_DOCKER") == "1":
            # This environment variable is set in the Docker image. Makes sure a new driver
            # is not downloaded as the Docker image already has the correct driver
            driver_version = "keep"

        driver = Driver(
            binary_location=browser_path,
            driver_version=driver_version,
            headless=True,
            uc_cdp_events=True,
            undetectable=True,
        )
        logger.debug("Using browser version: %s", driver.caps["browserVersion"])

        driver.add_cdp_listener("Network.requestWillBeSent", self._headers_listener)

        logger.debug("Loading Southwest Check-In page")
        driver.get(CHECKIN_URL)
        return driver

    def _headers_listener(self, data: JSON) -> None:
        """
        Wait for the correct URL request has gone through. Once it has, set the headers
        in the checkin_scheduler.
        """
        request = data["params"]["request"]
        if request["url"] in HEADERS_URLS and not self.headers_set:
            self.checkin_scheduler.headers = self._get_needed_headers(request["headers"])
            self.headers_set = True

    def _login_listener(self, data: JSON) -> None:
        """
        Wait for various responses that are needed once the account is logged in. The request IDs
        are kept track of to get the response body associated with them later.
        """
        response = data["params"]["response"]
        if response["url"] == LOGIN_URL:
            logger.debug("Login response has been received")
            self.login_request_id = data["params"]["requestId"]
            self.login_status_code = response["status"]
        elif response["url"] == TRIPS_URL:
            logger.debug("Upcoming trips response has been received")
            self.trips_request_id = data["params"]["requestId"]

    def _wait_for_attribute(self, attribute: str) -> None:
        logger.debug("Waiting for %s to be set", attribute)
        while not getattr(self, attribute):
            time.sleep(0.5)

        logger.debug("%s set successfully", attribute)

    def _wait_for_login(self, driver: Driver, account_monitor: AccountMonitor) -> None:
        """
        Waits for the login request to go through and sets the account name appropriately.
        Handles login errors, if necessary.
        """
        self._click_login_button(driver)
        self._wait_for_attribute("login_request_id")
        login_response = self._get_response_body(driver, self.login_request_id)

        # Handle login errors
        if self.login_status_code != 200:
            driver.quit()
            error = self._handle_login_error(login_response)
            raise error

        self._set_account_name(account_monitor, login_response)

    def _click_login_button(self, driver: Driver) -> None:
        """
        In some cases, the submit action on the login form may fail. Therefore, try clicking
        again, if necessary.
        """
        seleniumbase_actions.wait_for_element_not_visible(driver, ".dimmer")
        if driver.is_element_visible("div.popup"):
            # Don't attempt to click the login button again if the submission form went through,
            # yet there was an error
            return

        login_button = "button#login-btn"
        try:
            seleniumbase_actions.wait_for_element_not_visible(driver, login_button, timeout=5)
        except Exception:
            logger.debug("Login form failed to submit. Clicking login button again")
            driver.click(login_button)

    def _fetch_reservations(self, driver: Driver) -> List[JSON]:
        """
        Waits for the reservations request to go through and returns only reservations
        that are flights.
        """
        self._wait_for_attribute("trips_request_id")
        trips_response = self._get_response_body(driver, self.trips_request_id)
        reservations = trips_response["upcomingTripsPage"]
        return [reservation for reservation in reservations if reservation["tripType"] == "FLIGHT"]

    def _get_response_body(self, driver: Driver, request_id: str) -> JSON:
        response = driver.execute_cdp_cmd("Network.getResponseBody", {"requestId": request_id})
        return json.loads(response["body"])

    def _handle_login_error(self, response: JSON) -> LoginError:
        if response.get("code") == INVALID_CREDENTIALS_CODE:
            logger.debug("Invalid credentials provided when attempting to log in")
            reason = "Invalid credentials"
        else:
            logger.debug("Logging in failed for an unknown reason")
            reason = "Unknown"

        return LoginError(reason, self.login_status_code)

    def _get_needed_headers(self, request_headers: JSON) -> JSON:
        headers = {}
        provided_headers = {
            "EE30zvQLWf-a": "BFcbo8GKyQoF5Hhzc-OaY=P7cltFq1RZcxQad9SciabmhGRr5nbdjsvOHeq00REGMmMCm6Y65O2ClE-IdPNyylpvxEIj=Pu0aRcK1yJU2WSsBMg5Su3J87YAIhXFBm92ps2Af17AqTLy7HwPuBVr_TUhLMb19xfi=Yaax-szeqpeJ_08y4OifE=_shVfezhVQGUrPxrpXCw2B5LFc6F5bYXHocAbLEuC_FxUbp4N9TjCG=BgeCGthW39EKFrHc9LsD5vWmqQ28sUTYV2KFmdKV6zH9Mim5928Wrv5uqVcdunRF6JvaJWbp8ZP3CCEdR8H5x6zfl6n0x9LK4VTwit1lL8GXf1sne4n-RM9oyt==6XA8irPxGRT62_8mQxnIAeovS0QgM_UBxVytsby-lcP8Sy51wy9cUP8wjbnCzsVxjFAKz47S7DOp7bhpvfWOpMcu_DLvO1w8hvF1=uzlB72mi-QTDq3zjWUb1LGr7=irxg6UbY1BubSPVmtV_l-V7hQOToAe9AYNDfGqeEANdGpoqVSyaGc-PEYAxBMQ8A7ysLeNvhlN_ZfWUUcjYHbpJMQH=TAsb6f6nuReFPyLLFcQ5gipYp8a9PBvGY=_HdnqrdcWnB_VMQ2rI9jCGRllvR2iVYrdccRMLsHJTpHS49tiDEDnhyyZO-EnZ7tXVQqvw8wZARdQKjh4zjv3R5IBUrQWvAZ2nPQcEd9WJtjH9=001FmvGPxR7UhPD2nxsIoG72tQ4_IYlnYvI-NZbg1ynU352ls7QqfW=edu6QY6SFb3bnEX8tF0eUaAhN2rIvBPmWfcxjZdPMbzj3mTw8zYvNNT1G3DvVbNrC4FgESxdT5=zjaTd27oDw=axgUXO5d4vFF9jp9sM39fI-R0oUEMh_wQzgWzGYbl5cHzy0lEaU5z8lyHfuBvHlIn8KKs0qVA6BESNYYE=U7rpFbsRJuzBSrgXK0cXj_GwmXflvT9WvNaT=7Q7fZcz6YAGY5nBiGsUgpl9X0erG=NNjN-2i0m7KblQ5iWAAUV9N3WSUALZ9BZeP0WXwAb7_DeC1P2WpYZDJCzGUMelK7m0jEIG_xF59Fo0RaJz=1-8B5Uq=Rx42n=Aao35KJCbHSei6DEv3WHyy00x=o5gQJzKx-Bcw73=rY4=bfwZ76uqndE5fCg7Dil_6-gGbmE6VvEcvAQN=epV22zhlhAtXtz8Mj7MLoKalgEtqM5LMOgQDHHAMo-9GT3pSzMNEFS86JZGMWdi5tBry=LQI9y335H5WYmxE1omh6wz9pDoagRfjx7uv08CEyBhwpXRzgCyJnCZJpMlys_hTpuN_a0izx2ml_IKV0HW=aECjKTEsmA-A4ps6D_=8jMxJLGa3qVNrY8V194RhA7qSt_57OupmD7RJd_3eSd_Tb4fjAt7inRQ4l_84Tl=bJW1tEHd-wuavOA7boNgwMaTaZ_T8qa_o3RuwcVNG7wLdhg_=TwSFy_yQx5o_3-spAH05glbl9cHPIR1rFW5m0fdeNAy9GLxgtbEYtb-1v-BbYKlasUejYfA6Vs_VvpGU-Q6=XP8i7A1QIZTCjOUxK85SxvrHlxcvyjeTRLdWlfz5qouxmYrKHqfltB5RvghSBBfQx4yTpiCoJU2zEcKbHh-XsJb4tOPmL61Alg2RIF62_zj4zguQo6mrd1P2T_nVcx5U-u9azopZs6AwqgThRmiUY1U=_lQv3gXOEQvKa6vaLStMiLTmIqem",
            "EE30zvQLWf-b": "9itzgj",
            "EE30zvQLWf-c": "AOBMPsePAQAAZaU9mOfybjfx1mBTu4mxSkpq0YqV9jhACUvyk6HBx-c6Z5MJ",
            "EE30zvQLWf-d": "ABaAhIDBCKGFgQGAAYIQgISigaIAwBGAzvpizi_33wehwcfnOmeTCf_____K8KYjANRGJUSDKNY53mC9PBWb0eY",
            "EE30zvQLWf-f": "A8LBQMePAQAAKu8x0Jq1eMaVfIQrh5jfqZApXNH9VwFaYUDaw5hHS_D5tVQlAUswJ0r6KwsEzIheCOfvosJeCA==",
            "EE30zvQLWf-z": "q"
        }
        for header in request_headers:
            if re.match(r"x-api-key|x-channel-id|user-agent|^[\w-]+?-\w$", header, re.I):
                if header in provided_headers:
                    headers[header] = provided_headers[header]
                else:
                    headers[header] = request_headers[header]

        return headers

    def _set_account_name(self, account_monitor: AccountMonitor, response: JSON) -> None:
        if account_monitor.first_name:
            # No need to set the name if this isn't the first time logging in
            return

        logger.debug("First time logging in. Setting account name")
        account_monitor.first_name = response["customers.userInformation.firstName"]
        account_monitor.last_name = response["customers.userInformation.lastName"]

        print(
            f"Successfully logged in to {account_monitor.first_name} "
            f"{account_monitor.last_name}'s account\n"
        )  # Don't log as it contains sensitive information
