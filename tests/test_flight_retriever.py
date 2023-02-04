import pytest
from pytest_mock import MockerFixture

from lib.checkin_scheduler import CheckInScheduler
from lib.config import Config
from lib.flight_retriever import AccountFlightRetriever, FlightRetriever
from lib.general import LoginError
from lib.notification_handler import NotificationHandler
from lib.webdriver import WebDriver

# This needs to be accessed to be tested
# pylint: disable=protected-access


# Don't read the config file
@pytest.fixture(autouse=True)
def mock_config(mocker: MockerFixture) -> None:
    mocker.patch("lib.flight_retriever.Config._read_config")


def test_flight_retriever_schedules_reservations_correctly(mocker: MockerFixture) -> None:
    mock_schedule = mocker.patch.object(CheckInScheduler, "schedule")
    flights = [{"confirmationNumber": "Test1"}, {"confirmationNumber": "Test2"}]

    test_retriever = FlightRetriever(Config())
    test_retriever.schedule_reservations(flights)

    mock_schedule.assert_called_once_with(["Test1", "Test2"])


def test_account_FR_monitors_the_account_continuously(mocker: MockerFixture) -> None:
    # Since the monitor_account function runs in an infinite loop, throw an Exception
    # when the sleep function is called a second time to break out of the loop.
    mocker.patch("time.sleep", side_effect=["", Exception])
    mock_get_flights = mocker.patch.object(AccountFlightRetriever, "_get_flights")
    mock_schedule_reservations = mocker.patch.object(FlightRetriever, "schedule_reservations")
    mock_remove_departed_flights = mocker.patch.object(CheckInScheduler, "remove_departed_flights")

    test_retriever = AccountFlightRetriever(Config(), "", "")

    with pytest.raises(Exception):
        test_retriever.monitor_account()

    assert mock_get_flights.call_count == 2
    assert mock_schedule_reservations.call_count == 2
    assert mock_remove_departed_flights.call_count == 2


def test_get_flights_exits_on_login_error(mocker: MockerFixture) -> None:
    mocker.patch.object(WebDriver, "get_flights", side_effect=LoginError)
    mock_failed_login = mocker.patch.object(NotificationHandler, "failed_login")

    with pytest.raises(SystemExit):
        test_retriever = AccountFlightRetriever(Config(), "", "")
        test_retriever._get_flights()

    mock_failed_login.assert_called_once()


def test_get_flights_returns_the_correct_flights(mocker: MockerFixture) -> None:
    flights = [{"flight1": "test1"}, {"flight2": "test2"}]
    mocker.patch.object(WebDriver, "get_flights", return_value=flights)

    test_retriever = AccountFlightRetriever(Config(), "", "")
    new_flights = test_retriever._get_flights()

    assert new_flights == flights
