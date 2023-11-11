"""Runs a mock check-in for the CheckInHandler"""

from datetime import datetime
from multiprocessing import Lock
from unittest.mock import call

import pytest
from pytest_mock import MockerFixture
from requests_mock import Mocker as RequestMocker

from lib.checkin_handler import CHECKIN_URL, CheckInHandler
from lib.flight import Flight
from lib.utils import BASE_URL


@pytest.fixture
def handler(mocker: MockerFixture) -> None:
    mock_scheduler = mocker.patch("lib.checkin_scheduler.CheckInScheduler")
    flight_info = {
        "arrivalAirport": {"name": "test_inbound", "country": None},
        "departureAirport": {"code": "LAX", "name": "test_outbound"},
        "departureDate": "2021-12-06",
        "departureTime": "14:40",
        "flights": [{"number": "100"}],
    }
    flight = Flight(flight_info, "TEST")
    # Make sure it isn't affected by local time
    flight.departure_time = datetime(2021, 12, 6, 14, 40)
    return CheckInHandler(mock_scheduler, flight, Lock())


def test_check_in(
    requests_mock: RequestMocker, mocker: MockerFixture, handler: CheckInHandler
) -> None:
    mock_datetime = mocker.patch("lib.checkin_handler.datetime")
    mock_datetime.utcnow.side_effect = [
        datetime(2021, 12, 5, 13, 40),
        datetime(2021, 12, 5, 14, 20),
    ]
    mock_sleep = mocker.patch("time.sleep")

    handler.first_name = "Garry"
    handler.last_name = "Lin"

    get_response = {
        "checkInViewReservationPage": {
            "_links": {"checkIn": {"body": {"test": "checkin"}, "href": "/post_check_in"}}
        }
    }

    post_response = {
        "checkInConfirmationPage": {
            "flights": {
                "passengers": [
                    {"boardingGroup": "A", "boardingPosition": "42", "name": "Garry Lin"},
                    {"boardingGroup": "A", "boardingPosition": "43", "name": "Erin Lin"},
                ]
            }
        }
    }

    requests_mock.get(
        BASE_URL + CHECKIN_URL + "TEST?first-name=Garry&last-name=Lin",
        [{"json": get_response, "status_code": 200}],
    )

    requests_mock.post(
        BASE_URL + "mobile-air-operations/post_check_in",
        [{"json": post_response, "status_code": 200}],
    )

    # pylint: disable-next=protected-access
    handler._set_check_in()

    mock_sleep.assert_has_calls([call(1795), call(1195)])
    handler.checkin_scheduler.refresh_headers.assert_called_once()
    handler.notification_handler.successful_checkin.assert_called_once()
