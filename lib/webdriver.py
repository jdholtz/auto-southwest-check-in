from __future__ import annotations

import json
import os
import re
import sys
import time
from typing import TYPE_CHECKING, Any, Dict, List

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    NoSuchElementException,
    TimeoutException
)

from .log import LOGS_DIRECTORY, get_logger
from .utils import DriverTimeoutError, LoginError, random_sleep_duration

if TYPE_CHECKING:
    from .checkin_scheduler import CheckInScheduler
    from .reservation_monitor import AccountMonitor

BASE_URL = "https://mobile.southwest.com"
LOGIN_URL = BASE_URL + "/api/security/v4/security/token"
TRIPS_URL = BASE_URL + "/api/mobile-misc/v1/mobile-misc/page/upcoming-trips"
HEADERS_URL = BASE_URL + "/api/chase/v2/chase/offers"

# Southwest's code when logging in with the incorrect information
INVALID_CREDENTIALS_CODE = 400518024

WAIT_TIMEOUT_SECS = 180

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

    def _take_debug_screenshot(self, driver: webdriver.Chrome, name: str) -> None:
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
        driver.execute_cdp_cmd("Network.responseReceived", self._login_listener)

        logger.debug("Logging into account to get a list of reservations and valid headers")

        # Log in to retrieve the account's reservations and needed headers for later requests
        self._wait_for_element_not_visible(driver, ".dimmer")
        self._take_debug_screenshot(driver, "pre_login.png")

        driver.find_element(By.CSS_SELECTOR, ".login-button--box").click()
        time.sleep(random_sleep_duration(1, 5))
        driver.find_element(By.CSS_SELECTOR, 'input[name="userNameOrAccountNumber"]').send_keys(account_monitor.username)

        # Use quote_plus to workaround a x-www-form-urlencoded encoding bug on the mobile site
        driver.find_element(By.CSS_SELECTOR, 'input[name="password"]').send_keys(f"{account_monitor.password}\n")

        # Wait for the necessary information to be set
        self._wait_for_attribute("headers_set")
        self._wait_for_login(driver, account_monitor)
        self._take_debug_screenshot(driver, "post_login.png")

        # The upcoming trips page is also loaded when we log in, so we might as well grab it
        # instead of requesting again later
        reservations = self._fetch_reservations(driver)

        driver.quit()
        return reservations

    def _get_driver(self) -> webdriver.Chrome:
        logger.debug("Starting webdriver for current session")

        # Detect if running on a Raspberry Pi
        if self.is_raspberry_pi():
            logger.debug("Raspberry Pi detected. Using ARM-compatible Chromedriver.")
            chromedriver_path = "/usr/lib/chromium-browser/chromedriver"
            browser_path = "/usr/bin/chromium-browser"
        else:
            logger.debug("Not running on Raspberry Pi. Using default Chromedriver.")
            chromedriver_path = "/usr/lib/chromium-browser/chromedriver"
            browser_path = "chromium"

        driver_version = "mlatest"
        if os.environ.get("AUTO_SOUTHWEST_CHECK_IN_DOCKER") == "1":
            # This environment variable is set in the Docker image. Makes sure a new driver
            # is not downloaded as the Docker image already has the correct driver
            driver_version = "keep"

        # Configure Chrome options
        options = Options()
        options.binary_location = browser_path
        options.add_argument("--headless")  # Run headless for non-GUI environments
        options.add_argument("--disable-gpu")  # Disable GPU acceleration in headless mode
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")  # Overcome limited resource problems
        options.add_argument("--window-size=1920,1080")  # Set window size to avoid element overlap
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-infobars")
        options.add_argument("--start-maximized")

        # Initialize Selenium Service
        service = Service(executable_path=chromedriver_path)

        # Initialize Chrome WebDriver
        try:
            driver = webdriver.Chrome(service=service, options=options)
            logger.debug("Using browser version: %s", driver.capabilities["browserVersion"])
        except Exception as e:
            logger.error(f"Failed to initialize Chrome WebDriver: {e}")
            raise

        logger.debug("Loading Southwest home page (this may take a moment)")
        driver.get(BASE_URL)
        self._take_debug_screenshot(driver, "after_page_load.png")

        # Handle any pop-ups that may appear
        self._handle_popup(driver)

        # Proceed to click the placement link with explicit wait
        try:
            placement_link = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "(//div[@data-qa='placement-link'])[2]"))
            )
            placement_link.click()
            logger.debug("Clicked on the placement link successfully.")
        except ElementClickInterceptedException:
            logger.warning("Click intercepted. Attempting to click using JavaScript.")
            self._click_element_with_js(driver, placement_link)
        except Exception as e:
            logger.error(f"Failed to click on the placement link: {e}")
            self._take_debug_screenshot(driver, "click_error.png")
            driver.quit()
            raise

        return driver

    def _handle_popup(self, driver: webdriver.Chrome) -> None:
        """
        Detects and closes the pop-up if it appears.
        """
        try:
            # Wait for the pop-up to appear (if it does)
            popup = WebDriverWait(driver, 5).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "div.popup-head"))
            )
            logger.debug("Pop-up detected. Attempting to close it.")

            # Locate the close button within the pop-up
            close_button = popup.find_element(By.CSS_SELECTOR, "button.close-btn")  # Update selector as needed

            # Click the close button
            close_button.click()
            logger.debug("Pop-up closed successfully.")

            # Optionally, wait until the pop-up is no longer visible
            WebDriverWait(driver, 5).until(
                EC.invisibility_of_element_located((By.CSS_SELECTOR, "div.popup-head"))
            )
            logger.debug("Confirmed that the pop-up is no longer visible.")
        except (NoSuchElementException, TimeoutException) as e:
            logger.debug("No pop-up detected or failed to close pop-up: %s", e)
            # If no pop-up is detected, continue without raising an error
        except Exception as e:
            logger.error("An unexpected error occurred while handling pop-up: %s", e)
            self._take_debug_screenshot(driver, "popup_error.png")
            driver.quit()
            raise

    def _click_element_with_js(self, driver: webdriver.Chrome, element: webdriver.remote.webelement.WebElement) -> None:
        """
        Clicks an element using JavaScript as a fallback.
        """
        try:
            driver.execute_script("arguments[0].click();", element)
            logger.debug("Clicked on the element using JavaScript.")
        except Exception as e:
            logger.error(f"Failed to click on the element using JavaScript: {e}")
            self._take_debug_screenshot(driver, "js_click_error.png")
            driver.quit()
            raise

    def is_raspberry_pi(self) -> bool:
        """Detect if the system is a Raspberry Pi by checking /proc/cpuinfo."""
        try:
            with open("/proc/cpuinfo", "r") as f:
                info = f.read().lower()
            return "raspberry pi" in info
        except Exception:
            return False

    def _headers_listener(self, data: JSON) -> None:
        """
        Wait for the correct URL request has gone through. Once it has, set the headers
        in the checkin_scheduler.
        """
        request = data["params"]["request"]
        if request["url"] == HEADERS_URL:
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
        logger.debug("Waiting for %s to be set (timeout: %d seconds)", attribute, WAIT_TIMEOUT_SECS)
        poll_interval = 0.5

        attempts = 0
        max_attempts = int(WAIT_TIMEOUT_SECS / poll_interval)
        while not getattr(self, attribute) and attempts < max_attempts:
            time.sleep(poll_interval)
            attempts += 1

        if attempts >= max_attempts:
            timeout_err = DriverTimeoutError(f"Timeout waiting for the '{attribute}' attribute")
            logger.debug(timeout_err)
            raise timeout_err

        logger.debug("%s set successfully", attribute)

    def _wait_for_login(self, driver: webdriver.Chrome, account_monitor: AccountMonitor) -> None:
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

    def _click_login_button(self, driver: webdriver.Chrome) -> None:
        """
        In some cases, the submit action on the login form may fail. Therefore, try clicking
        again, if necessary.
        """
        self._wait_for_element_not_visible(driver, ".dimmer")
        try:
            popup = driver.find_element(By.CSS_SELECTOR, "div.popup")
            if popup.is_displayed():
                # Don't attempt to click the login button again if the submission form went through,
                # yet there was an error
                return
        except NoSuchElementException:
            pass

        login_button = "button#login-btn"
        try:
            WebDriverWait(driver, 5).until(
                EC.invisibility_of_element_located((By.CSS_SELECTOR, login_button))
            )
        except Exception:
            logger.debug("Login form failed to submit. Clicking login button again")
            driver.find_element(By.CSS_SELECTOR, login_button).click()

    def _fetch_reservations(self, driver: webdriver.Chrome) -> List[JSON]:
        """
        Waits for the reservations request to go through and returns only reservations
        that are flights.
        """
        self._wait_for_attribute("trips_request_id")
        trips_response = self._get_response_body(driver, self.trips_request_id)
        reservations = trips_response["upcomingTripsPage"]
        return [reservation for reservation in reservations if reservation["tripType"] == "FLIGHT"]

    def _get_response_body(self, driver: webdriver.Chrome, request_id: str) -> JSON:
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
        for header in request_headers:
            if re.match(r"x-api-key|x-channel-id|user-agent|^[\w-]+?-\w$", header, re.I):
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

    def _wait_for_element_not_visible(self, driver: webdriver.Chrome, css_selector: str) -> None:
        """Waits until the element specified by the CSS selector is not visible."""
        WebDriverWait(driver, WAIT_TIMEOUT_SECS).until(
            EC.invisibility_of_element_located((By.CSS_SELECTOR, css_selector))
        )
