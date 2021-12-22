from threading import Thread
from datetime import datetime, timedelta
import pytz
import requests
from time import sleep


BASE_URL = "https://mobile.southwest.com/api/"
CHECKIN_URL = "mobile-air-operations/v1/mobile-air-operations/page/check-in/"

class Flight:
    def __init__(self, account, confirmation_number, flight):
        self.account = account
        self.confirmation_number = confirmation_number
        self.departure_time = None
        self.departure_airport = None
        self.destination_airport = None
        self.get_flight_info(flight)
        x = Thread(target=self.set_check_in)
        x.start()

    def get_flight_info(self, flight):
        self.departure_airport = flight["departureAirport"]["name"]
        self.destination_airport = flight["arrivalAirport"]["name"]
        self.departure_time = self.get_flight_time(flight)

    def get_flight_time(self, flight):
        flight_date = f"{flight['departureDate']} {flight['departureTime']}"
        departure_airport_code = flight['departureAirport']['code']
        airport_timezone = self.get_airport_timezone(departure_airport_code)
        flight_time = self.convert_to_utc(flight_date, airport_timezone)

        return flight_time

    def get_airport_timezone(self, airport_code):
        airport_info = requests.post("https://openflights.org/php/apsearch.php", data={"iata": airport_code})
        airport_timezone = pytz.timezone(airport_info.json()['airports'][0]['tz_id'])

        return airport_timezone

    def convert_to_utc(self, flight_date, airport_timezone):
        flight_date = datetime.strptime(flight_date, "%Y-%m-%d %H:%M")
        flight_time = airport_timezone.localize(flight_date)
        utc_time = flight_time.astimezone(pytz.utc).replace(tzinfo=None)

        return utc_time

    def set_check_in(self):
        # Starts to check in five seconds early in case the Southwest server is ahead of your server
        checkin_time = self.departure_time - timedelta(days=1, seconds=5)

        current_time = datetime.utcnow()

        if checkin_time > current_time:
            print(f"Scheduling checkin to flight from '{self.departure_airport}' to '{self.destination_airport}' "
                  f"for {self.account.first_name} {self.account.last_name} at {checkin_time} UTC\n")

            # Refresh headers 10 minutes before to make sure they are valid
            sleep_time = (checkin_time - current_time - timedelta(minutes=10)).total_seconds()
            sleep(sleep_time)

            self.account.get_flights()
            current_time = datetime.utcnow()
            sleep_time = (checkin_time - current_time).total_seconds()
            sleep(sleep_time)

        self.check_in()
        self.account.flights.remove(self)

    def check_in(self):
        print(f"Checking in to flight from '{self.departure_airport}' to '{self.destination_airport}' "
              f"for {self.account.first_name} {self.account.last_name}\n")

        info = {"first-name": self.account.first_name, "last-name": self.account.last_name}
        site = CHECKIN_URL + self.confirmation_number

        response = self.make_request("GET", site, info)

        info = response['checkInViewReservationPage']['_links']['checkIn']
        site = f"mobile-air-operations{info['href']}"

        reservation = self.make_request("POST", site, info['body'])
        self.print_results(reservation['checkInConfirmationPage'])

    def make_request(self, method, site, info):
        url = BASE_URL + site

        # In the case that your server and the Southwest server aren't in sync,
        # this requests multiple times for a better chance at success
        attempts = 0
        while attempts < 20:
            if method == "POST":
                response = requests.post(url, headers=self.account.headers, json=info)
            elif method == "GET":
                response = requests.get(url, headers=self.account.headers, params=info)
            else:
                print(f"\033[91mError: Method {method} not known\033[0m")
                return

            if response.status_code == 200:
                return response.json()

            attempts += 1
            sleep(0.5)

        print(f"Failed to retrieve reservation. Reason: {response.reason} {response.status_code}")
        # TO-DO: Kill thread without killing other threads or the main process
        # The thread does not exit at the moment, it instead continues even after failing

    def print_results(self, boarding_pass):
        print(f"Successfully checked in to flight from '{self.departure_airport}' to '{self.destination_airport}'!")
        for flight in boarding_pass['flights']:
            for passenger in flight['passengers']:
                print(f"{passenger['name']} got {passenger['boardingGroup']}{passenger['boardingPosition']}!")
        print()
