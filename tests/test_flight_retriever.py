import pytest
from pytest_mock import MockerFixture

from lib.checkin_scheduler import CheckInScheduler
from lib.flight_retriever import AccountFlightRetriever, FlightRetriever
from lib.webdriver import WebDriver

# This needs to be accessed to be tested
# pylint: disable=protected-access


# Don't read the config file
@pytest.fixture(autouse=True)
def mock_config(mocker: MockerFixture) -> None:
    mocker.patch("lib.flight_retriever.Config._get_config")


def test_flight_retriever_schedules_reservations_correctly(mocker: MockerFixture) -> None:
    mock_schedule = mocker.patch.object(CheckInScheduler, "schedule")
    flights = [{"confirmationNumber": "Test1"}, {"confirmationNumber": "Test2"}]

    test_retriever = FlightRetriever()
    test_retriever.schedule_reservations(flights)

    mock_schedule.assert_called_once_with(["Test1", "Test2"])


def test_account_FR_monitors_the_account_continuously(mocker: MockerFixture) -> None:
    # Since the monitor_account function runs in an infinite loop, throw an Exception
    # when the sleep function is called a second time to break out of the loop.
    mocker.patch("time.sleep", side_effect=["", Exception])
    mock_get_flights = mocker.patch.object(AccountFlightRetriever, "_get_flights")
    mock_schedule_reservations = mocker.patch.object(FlightRetriever, "schedule_reservations")
    mock_remove_departed_flights = mocker.patch.object(CheckInScheduler, "remove_departed_flights")

    test_retriever = AccountFlightRetriever("", "")

    with pytest.raises(Exception):
        test_retriever.monitor_account()

    assert mock_get_flights.call_count == 2
    assert mock_schedule_reservations.call_count == 2
    assert mock_remove_departed_flights.call_count == 2


def test_get_flights_returns_the_correct_flights(mocker: MockerFixture) -> None:
    flights = [{"flight1": "test1"}, {"flight2": "test2"}]
    mocker.patch.object(WebDriver, "get_flights", return_value=flights)

    test_retriever = AccountFlightRetriever("", "")
    new_flights = test_retriever._get_flights()

    assert new_flights == flights
