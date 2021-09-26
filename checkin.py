from datetime import datetime, timedelta
import sys
import pytz
import requests

def check_in(confirmation_number, first_name, last_name):
    print(confirmation_number, first_name, last_name)
    checkin_time = get_checkin_time()
    print(checkin_time)

def get_checkin_time():
    flight_info = get_flight_info()
    flight_time = convert_to_utc_tz(flight_info)
    checkin_time = flight_time - timedelta(1)

    return checkin_time

def get_flight_info():
    headers = {"X-Channel-Id": "IOS", "X-Api-Key": "l7xx4eafc61ff199477ebe6dca005f47a7f1"}
    url = "https://mobile.southwest.com/api/mobile-air-booking/v1/mobile-air-booking/page/view-reservation/{}?first-name={}&last-name={}".format(confirmation_number, first_name, last_name)

    response = requests.get(url, headers=headers)

    # Only gets first flight listed
    # Todo: Add functionality for round-trip flights
    flight_info = response.json()['viewReservationViewPage']['bounds'][0]

    flight_date = '{} {}'.format(flight_info['departureDate'], flight_info['departureTime'])
    departure_airport = flight_info['departureAirport']['code']

    return [flight_date, departure_airport]

def convert_to_utc_tz(flight_info):
    airport_timezone = get_airport_timezone(flight_info)
    time = datetime.strptime(flight_info[0], "%Y-%m-%d %H:%M")
    local_time = airport_timezone.localize(time)
    utc_time = local_time.astimezone(pytz.utc)

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

    check_in(confirmation_number, first_name, last_name)
