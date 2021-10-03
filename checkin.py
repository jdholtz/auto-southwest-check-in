#!/usr/bin/python

import pytz
import requests
import sys
from datetime import datetime, timedelta
from scripts import reservation
from time import sleep


def set_up_check_in(flight):
    checkin_time = get_checkin_time(flight)
    print(checkin_time)
    current_time = datetime.utcnow()
    tomorrow_time = current_time + timedelta(days=1)

    while checkin_time > current_time:
        if checkin_time < tomorrow_time:
            sleep(checkin_time.total_seconds())
        else:
            sleep(24 * 60 * 60)
            checkin_time = get_checkin_time(flight)

        current_time = datetime.utcnow()
        tomorrow_time = current_time + timedelta(days=1)

    print("Checking in...")
    reservation.check_in(confirmation_number, first_name, last_name)

def get_checkin_time(flight):
    flight_time = convert_to_utc(flight)
    checkin_time = flight_time - timedelta(days=1)

    return checkin_time

def get_flights(confirmation_number, first_name, last_name):
    print(confirmation_number, first_name, last_name)
    info = { "first-name": first_name, "last-name": last_name}
    site = "mobile-air-booking/v1/mobile-air-booking/page/view-reservation/" + confirmation_number

    response = reservation.make_request("GET", site, info)

    flights = []
    flight_info = response['viewReservationViewPage']['bounds']

    for flight in flight_info:
        flight_date = '{} {}'.format(flight['departureDate'], flight['departureTime'])
        departure_airport = flight['departureAirport']['code']
        flights.append([flight_date, departure_airport])

    return flights

def convert_to_utc(flight_info):
    airport_timezone = get_airport_timezone(flight_info)
    time = datetime.strptime(flight_info[0], "%Y-%m-%d %H:%M")
    local_time = airport_timezone.localize(time)
    utc_time = local_time.astimezone(pytz.utc).replace(tzinfo=None)

    return utc_time

def get_airport_timezone(flight_info):
    airport_code = flight_info[1]
    airport_info = requests.post("https://openflights.org/php/apsearch.php", data={"iata": airport_code})
    airport_timezone = pytz.timezone(airport_info.json()['airports'][0]['tz_id'])

    return airport_timezone


if __name__ == "__main__":
    arguments = sys.argv

    confirmation_number = arguments[1]
    first_name = arguments[2]
    last_name = arguments[3]

    flights = get_flights(confirmation_number, first_name, last_name)
    for flight in flights:
        set_up_check_in(flight)
