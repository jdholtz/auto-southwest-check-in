from __future__ import annotations
import json
import re
import time
from typing import Any, Dict, Optional, TYPE_CHECKING

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from seleniumwire.undetected_chromedriver import Chrome, ChromeOptions

if TYPE_CHECKING:
    from account import Account

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:96.0) Gecko/20100101 Firefox/96.0"
BASE_URL = "https://mobile.southwest.com"
LOGIN_URL = BASE_URL + "/api/security/v4/security/token"
TRIPS_URL = BASE_URL + "/api/mobile-misc/v1/mobile-misc/page/upcoming-trips"
CHECKIN_URL = BASE_URL + "/check-in"
RESERVATION_URL = BASE_URL + "/api/mobile-air-operations/v1/mobile-air-operations/page/check-in/"


class WebDriver():
    # This is heavily based off of https://github.com/byalextran/southwest-headers/commit/d2969306edb0976290bfa256d41badcc9698f6ed
    def get_info(self, account: Optional[Account] = None) -> Dict[str, Any]:
        options = self._get_options()
        seleniumwire_options = {'disable_encoding': True}

        driver = Chrome(options=options, seleniumwire_options=seleniumwire_options)
        driver.scopes = [LOGIN_URL, TRIPS_URL, RESERVATION_URL] # Filter out unneeded URLs

        if account is None:
            info = self._get_checkin_info(driver)
        else:
            info = self._get_account_info(account, driver)

        driver.quit()

        return info

    def _get_checkin_info(self, driver: Chrome) -> Dict[str, Any]:
        driver.get(CHECKIN_URL)

        # Attempt a check in to retrieve the correct headers
        confirmation_element = WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.NAME, "recordLocator")))
        confirmation_element.send_keys("ABCDEF") # A valid confirmation number isn't needed

        first_name_element = WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.NAME, "firstName")))
        first_name_element.send_keys("John")

        last_name_element = WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.NAME, "lastName")))
        last_name_element.send_keys("Doe")

        last_name_element.submit()

        # Retrieving the headers could fail if the form isn't given enough time to submit
        time.sleep(10)

        request_headers = driver.requests[0].headers
        headers = self._get_needed_headers(request_headers)

        return headers

    def _get_account_info(self, account: Account, driver: Chrome) -> Dict[str, Any]:
        driver.get(BASE_URL)

        # Login to retrieve the account's trips and needed headers for later requests
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CLASS_NAME, "login-button--box"))).click()

        username_element = WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.NAME, "userNameOrAccountNumber")))
        username_element.send_keys(account.username)

        password_element = WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.NAME, "password")))
        password_element.send_keys(account.password)

        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.ID, "login-btn"))).submit()

        # Retrieving the headers could fail if the form isn't given enough time to submit
        time.sleep(10)

        request = driver.requests[0]
        request_headers = request.headers
        account.headers = self._get_needed_headers(request_headers)

        # If this is the first time logging in, the account name needs to be set because that info is needed later
        if account.first_name is None:
            response = json.loads(request.response.body)
            self._set_account_name(account, response)

        # This page is also loaded when we log in, so we might as well grab it instead of requesting again later
        flights = json.loads(driver.requests[1].response.body)['upcomingTripsPage']

        return flights

    def _get_options(self) -> ChromeOptions:
        options = ChromeOptions()
        options.add_argument("--headless")

        # Fixes issues when run as root
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        # Southwest detects headless browser user agents, so we have to set our own
        options.add_argument("--user-agent=" + USER_AGENT)

        return options

    def _get_needed_headers(self, request_headers: Dict[str, Any]) -> Dict[str, Any]:
        headers = {}
        for header in request_headers:
            if re.match("x-api-key|x-channel-id|user-agent|^[\w-]+?-\w$", header, re.I):
                headers[header] = request_headers[header]

        return headers

    def _set_account_name(self, account: Account, response: Dict[str, Any]) -> None:
        account.first_name = response['customers.userInformation.firstName']
        account.last_name = response['customers.userInformation.lastName']
