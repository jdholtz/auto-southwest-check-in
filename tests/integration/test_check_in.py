"""Runs a mock check-in for the CheckInHandler as well as a same-day flight check-in"""

import copy
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
        "flights": [{"number": "WN100"}],
    }
    flight = Flight(flight_info, {}, "TEST")
    # Make sure it isn't affected by local time
    flight.departure_time = datetime(2021, 12, 6, 14, 40)
    return CheckInHandler(mock_scheduler, flight, Lock())


@pytest.mark.parametrize("same_day_flight", [False, True])
def test_check_in(
    requests_mock: RequestMocker,
    mocker: MockerFixture,
    handler: CheckInHandler,
    same_day_flight: bool,
) -> None:
    mocker.patch(
        "lib.checkin_handler.get_current_time",
        side_effect=[
            datetime(2021, 12, 5, 13, 40),
            datetime(2021, 12, 5, 14, 20),
        ],
    )
    mock_sleep = mocker.patch("time.sleep")

    handler.first_name = "Garry"
    handler.last_name = "Lin"

    post_response1 = {
        "checkInViewReservationPage": {
            "_links": {"checkIn": {"body": {"test": "checkin"}, "href": "/post_check_in"}}
        }
    }

    post_response2 = {
        "checkInConfirmationPage": {
            "flights": [
                {
                    "passengers": [
                        {"boardingGroup": "A", "boardingPosition": "42", "name": "Garry Lin"},
                        {"boardingGroup": "A", "boardingPosition": "43", "name": "Erin Lin"},
                    ]
                }
            ]
        }
    }

    requests_mock.post(
        BASE_URL + CHECKIN_URL + "TEST",
        [{"json": post_response1, "status_code": 200}],
    )
    requests_mock.post(
        BASE_URL + "mobile-air-operations/post_check_in",
        [{"json": post_response2, "status_code": 200}],
    )

    if same_day_flight:
        # Add a flight before to make sure a same day flight selects the second flight
        same_day_post_response = copy.deepcopy(post_response2)
        same_day_post_response["checkInConfirmationPage"]["flights"].insert(0, {})

        requests_mock.post(
            BASE_URL + "mobile-air-operations/post_check_in",
            [
                {"json": post_response2, "status_code": 200},
                {"json": same_day_post_response, "status_code": 200},
            ],
        )

    handler.flight.is_same_day = same_day_flight
    # pylint: disable-next=protected-access
    handler._set_check_in()

    mock_sleep.assert_has_calls([call(1795), call(1195)])
    handler.checkin_scheduler.refresh_headers.assert_called_once()

    mock_successful_checkin = handler.notification_handler.successful_checkin
    mock_successful_checkin.assert_called_once()

    # Ensure all flights have been checked in
    checked_in_flights = mock_successful_checkin.call_args[0][0]["flights"]
    assert len(checked_in_flights) == 2 if same_day_flight else 1
