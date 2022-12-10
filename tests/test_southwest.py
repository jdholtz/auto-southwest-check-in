from typing import List

import pytest
from pytest_mock import MockerFixture

import southwest
from lib.checkin_scheduler import CheckInScheduler
from lib.flight_retriever import AccountFlightRetriever, FlightRetriever
from lib.notification_handler import NotificationHandler


# We don't actually want the config to read the file for these tests
@pytest.fixture(autouse=True)
def mock_config(mocker: MockerFixture) -> None:
    mocker.patch("lib.flight_retriever.Config")


@pytest.mark.parametrize("flag", ["-v", "--version"])
def test_set_up_prints_version_when_flag_is_passed(
    flag: str, capsys: pytest.CaptureFixture[str]
) -> None:
    southwest.set_up([flag])
    assert southwest.__version__ in capsys.readouterr().out


def test_set_up_sends_test_notifications_when_flag_is_passed(mocker: MockerFixture) -> None:
    mock_send_notification = mocker.patch.object(NotificationHandler, "send_notification")
    southwest.set_up(["--test-notifications"])
    mock_send_notification.assert_called_once()


def test_set_up_monitors_account_when_a_username_and_password_are_provided(
    mocker: MockerFixture,
) -> None:
    mock_account_FR = mocker.patch.object(AccountFlightRetriever, "__init__", return_value=None)
    mock_get_flights = mocker.patch.object(AccountFlightRetriever, "monitor_account")

    southwest.set_up(["username", "password"])

    mock_account_FR.assert_called_once_with("username", "password")
    mock_get_flights.assert_called_once()


def test_set_up_schedules_checkin_when_a_confirmation_number_and_name_are_provided(
    mocker: MockerFixture,
) -> None:
    # The Flight Retriever needs to be mocked to get the values passed in to the constructor, but
    # it still needs to return a valid Flight Retriever
    mock_flight_retriever = mocker.patch(
        "southwest.FlightRetriever", return_value=FlightRetriever()
    )

    mock_refresh_headers = mocker.patch.object(CheckInScheduler, "refresh_headers")
    mock_schedule_reservations = mocker.patch.object(FlightRetriever, "schedule_reservations")

    southwest.set_up(["000000", "first", "last"])

    mock_flight_retriever.assert_called_once_with("first", "last")
    mock_refresh_headers.assert_called_once()
    mock_schedule_reservations.assert_called_once_with([{"confirmationNumber": "000000"}])


@pytest.mark.parametrize("arguments", [[], ["1"], ["1", "2", "3", "4"]])
def test_set_up_sends_error_message_when_arguments_are_invalid(
    arguments: List[str], capsys: pytest.CaptureFixture[str]
) -> None:
    southwest.set_up(arguments)
    assert capsys.readouterr().out == "Invalid arguments\n"
