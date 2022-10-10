from typing import List

import pytest
from pytest_mock import MockerFixture

from lib.account import Account
import southwest


# We don't actually want the config to read the file for these tests
@pytest.fixture(autouse = True)
def mock_config(mocker: MockerFixture) -> None:
    mocker.patch("lib.account.Config", return_value = {})


def test_set_up_sends_test_notifications_when_flag_is_passed(
    mocker: MockerFixture
) -> None:
    mock_send_notification = mocker.patch.object(Account, "send_notification")
    southwest.set_up(["--test-notifications"])
    mock_send_notification.assert_called_once()


def test_set_up_retrieves_flights_when_a_username_and_password_are_provided(
    mocker: MockerFixture
) -> None:
    mock_account = mocker.patch.object(Account, "__init__", return_value = None)
    mock_get_flights = mocker.patch.object(Account, "get_flights")

    southwest.set_up(["username", "password"])

    mock_account.assert_called_once_with("username", "password")
    mock_get_flights.assert_called_once()


def test_set_up_retrieves_flight_info_when_a_confirmation_number_and_name_are_provided(
    mocker: MockerFixture
) -> None:
    mock_account = mocker.patch.object(Account, "__init__", return_value = None)
    mock_get_checkin_info = mocker.patch.object(Account, "get_checkin_info")

    southwest.set_up(["000000", "first", "last"])

    mock_account.assert_called_once_with(first_name = "first", last_name = "last")
    mock_get_checkin_info.assert_called_once_with("000000")


@pytest.mark.parametrize("arguments", [[], ["1"], ["1", "2", "3", "4"]])
def test_set_up_sends_error_message_when_arguments_are_invalid(
    arguments: List[str], capsys: pytest.CaptureFixture[str]
) -> None:
    southwest.set_up(arguments)
    assert capsys.readouterr().out == "Invalid arguments\n"
