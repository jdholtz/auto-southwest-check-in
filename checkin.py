#!/usr/bin/python
"""Automatically checks you in to your Southwest flight 24 hours beforehand

Usage: checkin.py CONFIRMATION_NUMBER FIRST_NAME LAST_NAME
"""

import pytz
import requests
import sys
from datetime import datetime, timedelta
from scripts import reservation
from time import sleep


def set_up_check_in(flight):
    checkin_time = get_checkin_time(flight)
    current_time = datetime.utcnow()
    tomorrow_time = current_time + timedelta(days=1)

    while checkin_time > current_time:
        if checkin_time < tomorrow_time:
            sleep(checkin_time.total_seconds())
        else:
            # Once a day, the script will check to see if the flight time has changed
            sleep(24*60*60)
            checkin_time = get_checkin_time(flight)

        current_time = datetime.utcnow()
        tomorrow_time = current_time + timedelta(days=1)

    print("Checking in...")
    reservation.check_in(confirmation_number, first_name, last_name)

def get_checkin_time(flight):
    flight_time = convert_to_utc(flight)
    # Starts to check in five seconds early in case the Southwest server is ahead of your server
    checkin_time = flight_time - timedelta(days=1, seconds=5)

    return checkin_time

def get_flights(confirmation_number, first_name, last_name):
    info = { "first-name": first_name, "last-name": last_name}
    site = "mobile-air-booking/v1/mobile-air-booking/page/view-reservation/" + confirmation_number

    response = reservation.make_request("GET", site, info)

    # If multiple flights are under the same confirmation number, it will schedule all checkins one by one
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
    flight_time = airport_timezone.localize(time)
    utc_time = flight_time.astimezone(pytz.utc).replace(tzinfo=None)

    return utc_time

def get_airport_timezone(flight_info):
    airport_code = flight_info[1]
    airport_info = requests.post("https://openflights.org/php/apsearch.php", data={"iata": airport_code})
    airport_timezone = pytz.timezone(airport_info.json()['airports'][0]['tz_id'])

    return airport_timezone


if __name__ == "__main__":
    arguments = sys.argv
    if arguments[1] == "-h" or arguments[1] == "--help":
        print(__doc__)
        sys.exit()

    confirmation_number = arguments[1]
    first_name = arguments[2]
    last_name = arguments[3]

    try:
        flights = get_flights(confirmation_number, first_name, last_name)
        for flight in flights:
            print("Scheduling checkin for {} {} at {} UTC".format(first_name, last_name, get_checkin_time(flight)))
            set_up_check_in(flight)

    except KeyboardInterrupt:
        print("\nCtrl+C pressed. Stopping checkin")
        sys.exit()
