import time
import requests
from .webdriver import WebDriver
from .flight import Flight


VIEW_RESERVATION_URL = "https://mobile.southwest.com/api/mobile-air-booking/v1/mobile-air-booking/page/view-reservation/"

class Account:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.first_name = None
        self.last_name = None
        self.flights = []
        self.headers = {}

    def get_flights(self):
        webdriver = WebDriver()
        reservations = webdriver.get_account_info(self)

        for reservation in reservations:
            self.get_reservation_info(reservation)

        return self.flights

    def get_reservation_info(self, flight):
        confirmation_number = flight['confirmationNumber']

        info = {"first-name": self.first_name, "last-name": self.last_name}
        site = VIEW_RESERVATION_URL + confirmation_number

        response = requests.get(site, headers=self.headers, params=info).json()

        # If multiple flights are under the same confirmation number, it will schedule all checkins one by one
        flight_info = response['viewReservationViewPage']['bounds']

        for flight in flight_info:
            if not flight in self.flights:
                flight = Flight(self, confirmation_number, flight)
                self.flights.append(flight)
