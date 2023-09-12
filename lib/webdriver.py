from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import TYPE_CHECKING, Any, Dict, List

from requests.compat import quote_plus
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from seleniumwire.request import Response
from seleniumwire.undetected_chromedriver import Chrome, ChromeOptions

from .log import get_logger
from .utils import LoginError

if TYPE_CHECKING:
    from .checkin_scheduler import CheckInScheduler
    from .reservation_monitor import AccountMonitor

BASE_URL = "https://mobile.southwest.com"
LOGIN_URL = BASE_URL + "/api/security/v4/security/token"
TRIPS_URL = BASE_URL + "/api/mobile-misc/v1/mobile-misc/page/upcoming-trips"
CHECKIN_URL = BASE_URL + "/check-in"
RESERVATION_URL = BASE_URL + "/api/mobile-air-operations/v1/mobile-air-operations/page/check-in/"

# Southwest's code when logging in with the incorrect information
INVALID_CREDENTIALS_CODE = 400518024

logger = get_logger(__name__)

# Temporary workaround to not log a warning message when not providing version_main. Can be removed
# once my PR gets merged (https://github.com/ultrafunkamsterdam/undetected-chromedriver/pull/1504)
logging.getLogger("uc").setLevel(logging.ERROR)


class WebDriver:
    """
    Controls fetching valid headers for use with the Southwest API.

    This class can be instantiated in two ways:
    1. Setting/refreshing headers before a check-in to ensure the headers are valid.
    To do this, a check-in form is filled out with invalid information (valid information
    is not necessary in this case).

    2. Logging into an account. In this case, the headers are refreshed and a list of scheduled
    flights are retrieved.

    Some of this code is based off of:
    https://github.com/byalextran/southwest-headers/commit/d2969306edb0976290bfa256d41badcc9698f6ed
    """

    def __init__(self, checkin_scheduler: CheckInScheduler) -> None:
        self.checkin_scheduler = checkin_scheduler
        self.seleniumwire_options = {"disable_encoding": True}

    def set_headers(self) -> None:
        """
        Fills out a check-in form with invalid information and grabs the valid
        headers from the request. Then, it updates the headers in the check-in scheduler.
        """
        driver = self._get_driver()
        logger.debug("Filling out a check-in form to get valid headers")

        # Attempt a check in to retrieve the correct headers
        confirmation_element = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.NAME, "recordLocator"))
        )
        confirmation_element.send_keys("ABCDEF")  # A valid confirmation number isn't needed

        first_name_element = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.NAME, "firstName"))
        )
        first_name_element.send_keys("John")

        last_name_element = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.NAME, "lastName"))
        )
        last_name_element.send_keys("Doe")
        last_name_element.submit()

        self._wait_for_response(driver, 0)
        self._set_headers_from_request(driver)
        self._quit_browser(driver)

    def get_reservations(self, account_monitor: AccountMonitor) -> List[Dict[str, Any]]:
        """
        Logs into the account being monitored to retrieve a list of reservations. Since
        valid headers are produced, they are also grabbed and updated in the check-in scheduler.
        Last, if the account name is not set, it will be set based on the response information.
        """
        driver = self._get_driver()
        logger.debug("Logging into account to get a list of reservations and valid headers")

        # Log in to retrieve the account's reservations and needed headers for later requests
        WebDriverWait(driver, 30).until(EC.invisibility_of_element((By.CLASS_NAME, "dimmer")))
        WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((By.CLASS_NAME, "login-button--box"))
        ).click()

        username_element = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.NAME, "userNameOrAccountNumber"))
        )
        username_element.send_keys(account_monitor.username)

        password_element = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.NAME, "password"))
        )

        # Use quote_plus to workaround a x-www-form-urlencoded encoding bug on the mobile site
        password_element.send_keys(quote_plus(account_monitor.password))
        password_element.submit()

        response = self._wait_for_response(driver, 0)
        if response.status_code != 200:
            self._quit_browser(driver)
            error = self._handle_login_error(response)
            raise error

        self._set_headers_from_request(driver)

        # If this is the first time logging in, the account name needs to be set
        # because that info is needed later
        if account_monitor.first_name is None:
            logger.debug("First time logging in. Setting account name")
            response_body = json.loads(response.body)
            self._set_account_name(account_monitor, response_body)
            print(
                f"Successfully logged in to {account_monitor.first_name} "
                f"{account_monitor.last_name}'s account\n"
            )  # Don't log as it contains sensitive information

        # This page is also loaded when we log in, so we might as well grab it instead of
        # requesting again later
        reservation_response = self._wait_for_response(driver, 1)
        reservations = json.loads(reservation_response.body)["upcomingTripsPage"]

        self._quit_browser(driver)

        return [reservation for reservation in reservations if reservation["tripType"] == "FLIGHT"]

    def _get_driver(self) -> Chrome:
        logger.debug("Starting webdriver for current session")
        driver = self._init_driver()

        # Delete any requests that could have been made while the driver was being initialized
        del driver.requests

        # Filter out unneeded URLs
        driver.scopes = [LOGIN_URL, TRIPS_URL, RESERVATION_URL]

        logger.debug("Loading Southwest Check-In page")
        driver.get(CHECKIN_URL)
        return driver

    def _init_driver(self) -> Chrome:
        """
        Attempt to initialize the driver multiple times. This is necessary because random
        initializations can occasionally occur. Trying multiple times makes the initialization
        more reliable.
        """
        chromedriver_path = self.checkin_scheduler.reservation_monitor.config.chromedriver_path
        chrome_version = self.checkin_scheduler.reservation_monitor.config.chrome_version

        max_attempts = 3
        attempts = 0
        while attempts < max_attempts:
            try:
                driver = Chrome(
                    driver_executable_path=chromedriver_path,
                    options=self._get_options(),
                    seleniumwire_options=self.seleniumwire_options,
                    version_main=chrome_version,
                )
                return driver
            except Exception as err:
                logger.debug(
                    "An exception occurred when initializing the webdriver: Name: %s. Error: %s",
                    type(err).__name__,
                    err,
                )
                attempts += 1
                logger.debug("%d more attempts", max_attempts - attempts)
                error = err

        raise RuntimeError(
            f"Failed to initialize the webdriver after {max_attempts} attempts"
        ) from error

    def _wait_for_response(self, driver: Chrome, response_num: int) -> Response:
        """
        Wait for the specified response from the driver. Gathering information from Southwest
        could fail if the responses aren't given enough time to be retrieved.
        """
        while (
            not driver.requests
            or len(driver.requests) < response_num + 1
            or not driver.requests[response_num].response
        ):
            time.sleep(0.5)

        return driver.requests[response_num].response

    def _set_headers_from_request(self, driver: Chrome) -> None:
        logger.debug("Setting valid headers from previous request")
        request_headers = driver.requests[0].headers
        self.checkin_scheduler.headers = self._get_needed_headers(request_headers)

    def _get_options(self) -> ChromeOptions:
        options = ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--disable-dev-shm-usage")  # For docker containers
        options.add_argument("--no-sandbox") # Run in docker containers without SYS_ADMIN or --privileged mode

        # This is a temporary workaround due to incompatibilities between selenium-wire and
        # Selenium 4.10+. Can be removed when it is either fixed in Selenium Wire (see my PR
        # here: https://github.com/wkeeling/selenium-wire/pull/699) or in Undetected
        # Chromdriver (see my PR here:
        # https://github.com/ultrafunkamsterdam/undetected-chromedriver/pull/1503)
        options.set_capability("acceptInsecureCerts", True)
        return options

    def _handle_login_error(self, response: Response) -> LoginError:
        body = json.loads(response.body)
        if body.get("code") == INVALID_CREDENTIALS_CODE:
            logger.debug("Invalid credentials provided when attempting to log in")
            reason = "Invalid credentials"
        else:
            logger.debug("Logging in failed for an unknown reason")
            reason = "Unknown"

        return LoginError(reason, response.status_code)

    def _get_needed_headers(self, request_headers: Dict[str, Any]) -> Dict[str, Any]:
        headers = {}
        for header in request_headers:
            if re.match(r"x-api-key|x-channel-id|user-agent|^[\w-]+?-\w$", header, re.I):
                headers[header] = request_headers[header]

        return headers

    def _set_account_name(self, account_monitor: AccountMonitor, response: Dict[str, Any]) -> None:
        account_monitor.first_name = response["customers.userInformation.firstName"]
        account_monitor.last_name = response["customers.userInformation.lastName"]

    def _quit_browser(self, driver: Chrome) -> None:
        driver.quit()

        # Can be removed when my PR in Undetected Chromedriver is merged:
        # https://github.com/ultrafunkamsterdam/undetected-chromedriver/pull/1391
        try:
            # Wait so zombie (defunct) processes are not created
            os.waitpid(driver.browser_pid, 0)
            os.waitpid(driver.service.process.pid, 0)
        except ChildProcessError:
            # Processes are cleaned up without needing waitpid on Windows
            pass
