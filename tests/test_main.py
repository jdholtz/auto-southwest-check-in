from typing import List

import pytest
from pytest_mock import MockerFixture

from lib import main
from lib.checkin_scheduler import CheckInScheduler
from lib.flight_retriever import AccountFlightRetriever, FlightRetriever
from lib.notification_handler import NotificationHandler


# We don't actually want the config to read the file for these tests
@pytest.fixture(autouse=True)
def mock_config(mocker: MockerFixture) -> None:
    mocker.patch("lib.flight_retriever.Config")


def test_print_version_prints_script_version(capsys: pytest.CaptureFixture[str]) -> None:
    main.print_version()
    assert main.__version__ in capsys.readouterr().out


def test_print_usage_prints_script_usage(capsys: pytest.CaptureFixture[str]) -> None:
    main.print_usage()
    output = capsys.readouterr().out
    assert main.__version__ in output
    assert main.USAGE in output


@pytest.mark.parametrize("flag", ["-v", "--version"])
def test_check_flags_prints_version_when_version_flag_is_passed(
    mocker: MockerFixture,
    flag: str,
) -> None:
    mock_exit = mocker.patch("sys.exit")
    mock_print_version = mocker.patch("lib.main.print_version")
    main.check_flags([flag])
    mock_print_version.assert_called_once()
    mock_exit.assert_called_once()


@pytest.mark.parametrize("arguments", [["-h"], ["--help"], []])
def test_check_flags_prints_usage_when_help_flag_is_passed(
    mocker: MockerFixture,
    arguments: List[str],
) -> None:
    mock_exit = mocker.patch("sys.exit")
    mock_print_usage = mocker.patch("lib.main.print_usage")
    main.check_flags(arguments)
    mock_print_usage.assert_called_once()
    mock_exit.assert_called_once()


def test_check_flags_does_not_exit_when_flags_are_not_matched(
    mocker: MockerFixture,
) -> None:
    mock_exit = mocker.patch("sys.exit")
    main.check_flags(["--invalid-flag"])
    mock_exit.assert_not_called()


def test_set_up_sends_test_notifications_when_flag_is_passed(mocker: MockerFixture) -> None:
    mock_send_notification = mocker.patch.object(NotificationHandler, "send_notification")
    main.set_up(["--test-notifications"])
    mock_send_notification.assert_called_once()


def test_set_up_monitors_account_when_a_username_and_password_are_provided(
    mocker: MockerFixture,
) -> None:
    mock_account_FR = mocker.patch.object(AccountFlightRetriever, "__init__", return_value=None)
    mock_get_flights = mocker.patch.object(AccountFlightRetriever, "monitor_account")

    main.set_up(["username", "password"])

    mock_account_FR.assert_called_once_with("username", "password")
    mock_get_flights.assert_called_once()


def test_set_up_schedules_checkin_when_a_confirmation_number_and_name_are_provided(
    mocker: MockerFixture,
) -> None:
    # The Flight Retriever needs to be mocked to get the values passed in to the constructor, but
    # it still needs to return a valid Flight Retriever
    mock_flight_retriever = mocker.patch(
        "lib.flight_retriever.FlightRetriever", return_value=FlightRetriever()
    )

    mock_refresh_headers = mocker.patch.object(CheckInScheduler, "refresh_headers")
    mock_schedule_reservations = mocker.patch.object(FlightRetriever, "schedule_reservations")

    main.set_up(["000000", "first", "last"])

    mock_flight_retriever.assert_called_once_with("first", "last")
    mock_refresh_headers.assert_called_once()
    mock_schedule_reservations.assert_called_once_with([{"confirmationNumber": "000000"}])


@pytest.mark.parametrize("arguments", [[], ["1"], ["1", "2", "3", "4"]])
def test_set_up_sends_error_message_when_arguments_are_invalid(
    arguments: List[str], capsys: pytest.CaptureFixture[str]
) -> None:
    main.set_up(arguments)
    output = capsys.readouterr().out
    assert "Invalid arguments" in output
    assert "--help" in output


def test_main_sets_up_script(mocker: MockerFixture) -> None:
    mock_check_flags = mocker.patch("lib.main.check_flags")
    mock_set_up = mocker.patch("lib.main.set_up")
    arguments = ["test", "arguments"]

    main.main(arguments)
    mock_check_flags.assert_called_once_with(arguments)
    mock_set_up.assert_called_once_with(arguments)
