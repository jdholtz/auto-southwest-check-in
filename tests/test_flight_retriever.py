from datetime import datetime

import pytest
from pytest_mock import MockerFixture

from lib.checkin_scheduler import CheckInScheduler
from lib.config import Config
from lib.fare_checker import FareChecker
from lib.flight_retriever import AccountFlightRetriever, FlightRetriever
from lib.notification_handler import NotificationHandler
from lib.utils import LoginError, RequestError
from lib.webdriver import WebDriver

# This needs to be accessed to be tested
# pylint: disable=protected-access


# Don't read the config file
@pytest.fixture(autouse=True)
def mock_config(mocker: MockerFixture) -> None:
    mocker.patch("lib.flight_retriever.Config._read_config")


def test_flight_retriever_monitors_flights_continuously(mocker: MockerFixture) -> None:
    # Since the monitor_flights function runs in an infinite loop, throw an Exception
    # when the sleep function is called a second time to break out of the loop.
    mocker.patch.object(FlightRetriever, "_smart_sleep", side_effect=["", Exception])
    mock_schedule_reservations = mocker.patch.object(FlightRetriever, "_schedule_reservations")
    mock_remove_departed_flights = mocker.patch.object(CheckInScheduler, "remove_departed_flights")
    mock_check_flight_fares = mocker.patch.object(FlightRetriever, "_check_flight_fares")

    test_retriever = FlightRetriever(Config())
    test_retriever.checkin_scheduler.flights = ["test_flight"]

    with pytest.raises(Exception):
        test_retriever.monitor_flights([{"test": "flight"}])

    mock_schedule_reservations.assert_called_once_with([{"test": "flight"}])
    assert mock_remove_departed_flights.call_count == 2
    assert mock_check_flight_fares.call_count == 2


def test_flight_retriever_stops_monitoring_when_no_flights_are_scheduled(
    mocker: MockerFixture,
) -> None:
    mock_smart_sleep = mocker.patch.object(FlightRetriever, "_smart_sleep")
    mock_schedule_reservations = mocker.patch.object(FlightRetriever, "_schedule_reservations")
    mock_remove_departed_flights = mocker.patch.object(CheckInScheduler, "remove_departed_flights")
    mock_check_flight_fares = mocker.patch.object(FlightRetriever, "_check_flight_fares")

    test_retriever = FlightRetriever(Config())
    test_retriever.monitor_flights([])

    mock_schedule_reservations.assert_called_once()
    mock_remove_departed_flights.assert_called_once()
    mock_check_flight_fares.assert_called_once()
    mock_smart_sleep.assert_not_called()


def test_flight_retriever_monitors_flights_once_if_retrieval_interval_is_zero(
    mocker: MockerFixture,
) -> None:
    mock_smart_sleep = mocker.patch.object(FlightRetriever, "_smart_sleep")
    mock_schedule_reservations = mocker.patch.object(FlightRetriever, "_schedule_reservations")
    mock_remove_departed_flights = mocker.patch.object(CheckInScheduler, "remove_departed_flights")
    mock_check_flight_fares = mocker.patch.object(FlightRetriever, "_check_flight_fares")

    config = Config()
    config.retrieval_interval = 0
    test_retriever = FlightRetriever(config)
    test_retriever.checkin_scheduler.flights = ["test_flight"]

    test_retriever.monitor_flights([])

    mock_schedule_reservations.assert_called_once()
    mock_remove_departed_flights.assert_called_once()
    mock_check_flight_fares.assert_called_once()
    mock_smart_sleep.assert_not_called()


def test_flight_retriever_schedules_reservations_correctly(mocker: MockerFixture) -> None:
    mock_schedule = mocker.patch.object(CheckInScheduler, "schedule")
    flights = [{"confirmationNumber": "Test1"}, {"confirmationNumber": "Test2"}]

    test_retriever = FlightRetriever(Config())
    test_retriever._schedule_reservations(flights)

    mock_schedule.assert_called_once_with(["Test1", "Test2"])


def test_flight_retriever_does_not_check_fares_if_configuration_is_false(
    mocker: MockerFixture,
) -> None:
    mock_fare_checker = mocker.patch("lib.flight_retriever.FareChecker")

    test_retriever = FlightRetriever(Config())
    test_retriever.config.check_fares = False
    test_retriever._check_flight_fares()

    mock_fare_checker.assert_not_called()


def test_flight_retriever_checks_fares_on_all_flights(mocker: MockerFixture) -> None:
    mock_check_flight_price = mocker.patch.object(FareChecker, "check_flight_price")

    test_retriever = FlightRetriever(Config())
    test_retriever.config.check_fares = True
    test_retriever.checkin_scheduler.flights = ["test_flight1", "test_flight2"]
    test_retriever._check_flight_fares()

    assert mock_check_flight_price.call_count == len(test_retriever.checkin_scheduler.flights)


def test_flight_retriever_catches_error_when_checking_fares(mocker: MockerFixture) -> None:
    mock_check_flight_price = mocker.patch.object(
        FareChecker, "check_flight_price", side_effect=["", RequestError]
    )

    test_retriever = FlightRetriever(Config())
    test_retriever.config.check_fares = True
    test_retriever.checkin_scheduler.flights = ["test_flight1", "test_flight2"]
    test_retriever._check_flight_fares()

    assert mock_check_flight_price.call_count == len(test_retriever.checkin_scheduler.flights)


def test_flight_retriever_smart_sleeps(mocker: MockerFixture) -> None:
    mock_sleep = mocker.patch("time.sleep")
    mock_datetime = mocker.patch("lib.flight_retriever.datetime")
    mock_datetime.utcnow.return_value = datetime(1999, 12, 31)

    test_retriever = FlightRetriever(Config())
    test_retriever.config.retrieval_interval = 24 * 60 * 60
    test_retriever._smart_sleep(datetime(1999, 12, 30, 12))

    mock_sleep.assert_called_once_with(12 * 60 * 60)


def test_account_FR_monitors_the_account_continuously(mocker: MockerFixture) -> None:
    # Since the monitor_account function runs in an infinite loop, throw an Exception
    # when the sleep function is called a second time to break out of the loop.
    mocker.patch.object(FlightRetriever, "_smart_sleep", side_effect=["", Exception])
    mock_get_flights = mocker.patch.object(AccountFlightRetriever, "_get_flights")
    mock_schedule_reservations = mocker.patch.object(FlightRetriever, "_schedule_reservations")
    mock_remove_departed_flights = mocker.patch.object(CheckInScheduler, "remove_departed_flights")
    mock_check_flight_fares = mocker.patch.object(FlightRetriever, "_check_flight_fares")

    test_retriever = AccountFlightRetriever(Config(), "", "")

    with pytest.raises(Exception):
        test_retriever.monitor_account()

    assert mock_get_flights.call_count == 2
    assert mock_schedule_reservations.call_count == 2
    assert mock_remove_departed_flights.call_count == 2
    assert mock_check_flight_fares.call_count == 2


def test_account_FR_checks_flights_once_if_retrieval_interval_is_zero(
    mocker: MockerFixture,
) -> None:
    mock_smart_sleep = mocker.patch.object(FlightRetriever, "_smart_sleep")
    mock_get_flights = mocker.patch.object(AccountFlightRetriever, "_get_flights")
    mock_schedule_reservations = mocker.patch.object(FlightRetriever, "_schedule_reservations")
    mock_remove_departed_flights = mocker.patch.object(CheckInScheduler, "remove_departed_flights")
    mock_check_flight_fares = mocker.patch.object(FlightRetriever, "_check_flight_fares")

    config = Config()
    config.retrieval_interval = 0
    test_retriever = AccountFlightRetriever(config, "", "")

    test_retriever.monitor_account()

    mock_smart_sleep.assert_not_called()
    mock_get_flights.assert_called_once()
    mock_schedule_reservations.assert_called_once()
    mock_remove_departed_flights.assert_called_once()
    mock_check_flight_fares.assert_called_once()


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
