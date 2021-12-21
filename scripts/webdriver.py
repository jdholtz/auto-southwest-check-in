import json
import re
import time
import seleniumwire.undetected_chromedriver.v2 as uc
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By


USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:96.0) Gecko/20100101 Firefox/96.0"
BASE_URL = "https://mobile.southwest.com"
LOGIN_URL = BASE_URL + "/api/security/v4/security/token"
TRIPS_URL = BASE_URL + "/api/mobile-misc/v1/mobile-misc/page/upcoming-trips"

class WebDriver():
    # This is heavily based off of https://github.com/byalextran/southwest-headers/commit/d2969306edb0976290bfa256d41badcc9698f6ed
    def get_account_info(self, account):
        options = self.get_options()
        seleniumwire_options = {'disable_encoding': True}

        driver = uc.Chrome(options=options, seleniumwire_options=seleniumwire_options)
        driver.scopes = [LOGIN_URL, TRIPS_URL] # Filter out unneeded URLs
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
        account.headers = self.get_needed_headers(request_headers)

        # If this is the first time logging in, the account name needs to be set because that info is needed later
        if account.first_name is None:
            response = json.loads(request.response.body)
            self.set_account_name(account, response)

        # This page is also loaded when we log in, so we might as well grab it instead of requesting again later
        flights = json.loads(driver.requests[1].response.body)['upcomingTripsPage']

        driver.quit()

        return flights

    def get_options(self):
        options = uc.ChromeOptions()
        options.add_argument("--headless")

        # Fixes issues when run as root
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        # Southwest detects headless browser user agents, so we have to set our own
        options.add_argument("--user-agent=" + USER_AGENT)
        return options

    def get_needed_headers(self, request_headers):
        headers = {}
        for header in request_headers:
            if re.match("x-api-key|x-user-experience-id|x-channel-id|^[\w-]+?-\w$", header, re.I):
                headers[header] = request_headers[header]

        return headers

    def set_account_name(self, account, response):
        account.first_name = response['customers.userInformation.firstName']
        account.last_name = response['customers.userInformation.lastName']
