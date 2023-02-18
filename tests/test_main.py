import logging
from typing import List
from unittest import mock

import pytest
from pytest_mock import MockerFixture

from lib import main
from lib.config import Config
from lib.notification_handler import NotificationHandler

# Don't write logs to a file during testing
main.LOG_FILE = "/dev/null"


# We don't actually want the config to read the file for these tests
@pytest.fixture(autouse=True)
def mock_config(mocker: MockerFixture) -> None:
    mocker.patch("lib.config.Config._read_config")


def test_print_version_prints_script_version(capsys: pytest.CaptureFixture[str]) -> None:
    main.print_version()
    assert main.__version__ in capsys.readouterr().out


def test_print_usage_prints_script_usage(capsys: pytest.CaptureFixture[str]) -> None:
    main.print_usage()
    output = capsys.readouterr().out
    assert main.__version__ in output
    assert main.__doc__ in output


@pytest.mark.parametrize("flag", ["-V", "--version"])
def test_check_flags_prints_version_when_version_flag_is_passed(
    mocker: MockerFixture,
    flag: str,
) -> None:
    mock_print_version = mocker.patch("lib.main.print_version")

    with pytest.raises(SystemExit):
        main.check_flags([flag])

    mock_print_version.assert_called_once()


@pytest.mark.parametrize("arguments", [["-h"], ["--help"]])
def test_check_flags_prints_usage_when_help_flag_is_passed(
    mocker: MockerFixture,
    arguments: List[str],
) -> None:
    mock_print_usage = mocker.patch("lib.main.print_usage")

    with pytest.raises(SystemExit):
        main.check_flags(arguments)

    mock_print_usage.assert_called_once()


def test_check_flags_does_not_exit_when_flags_are_not_matched(
    mocker: MockerFixture,
) -> None:
    mock_exit = mocker.patch("sys.exit")
    main.check_flags(["--invalid-flag"])
    mock_exit.assert_not_called()


@pytest.mark.parametrize(
    ["arguments", "verbosity_level"],
    [
        ([], logging.INFO),
        (["-v"], logging.DEBUG),
        (["--verbose"], logging.DEBUG),
    ],
)
def test_init_logging_sets_verbosity_level_correctly(
    mocker: MockerFixture,
    arguments: List[str],
    verbosity_level: int,
) -> None:
    mock_makedirs = mocker.patch("os.makedirs")

    # Don't actually rollover during testing
    mocker.patch.object(logging.handlers.RotatingFileHandler, "doRollover")

    main.init_logging(arguments)
    logger = logging.getLogger("lib")

    mock_makedirs.assert_called_once()
    assert len(logger.handlers) == 2
    assert logger.handlers[1].level == verbosity_level

    # Reset logger handlers so they don't carry to the next test
    logger.handlers = []


def test_set_up_accounts_starts_all_accounts_in_proceses(mocker: MockerFixture) -> None:
    config = Config()
    config.accounts = [["user1", "pass1"], ["user2", "pass2"]]

    mock_process = mocker.patch("lib.main.Process")
    mock_process.start = mock.Mock()

    main.set_up_accounts(config)

    assert mock_process.call_count == len(config.accounts)
    assert mock_process.return_value.start.call_count == len(config.accounts)


def test_set_up_flights_starts_all_flights_in_proceses(mocker: MockerFixture) -> None:
    config = Config()
    config.flights = [["test1", "first1", "last1"], ["test2", "first2", "last2"]]

    mock_process = mocker.patch("lib.main.Process")
    mock_process.start = mock.Mock()

    main.set_up_flights(config)

    assert mock_process.call_count == len(config.flights)
    assert mock_process.return_value.start.call_count == len(config.flights)


def test_set_up_check_in_sends_test_notifications_when_flag_is_passed(
    mocker: MockerFixture,
) -> None:
    mock_send_notification = mocker.patch.object(NotificationHandler, "send_notification")
    main.set_up(["--test-notifications"])
    mock_send_notification.assert_called_once()


@pytest.mark.parametrize(
    ["arguments", "accounts_len", "flights_len"],
    [
        ([], 0, 0),
        (["username", "password"], 1, 0),
        (["test", "John", "Doe"], 0, 1),
    ],
)
def test_set_up_check_in_sets_up_account_and_flight_with_arguments(
    mocker: MockerFixture, arguments: List[str], accounts_len: int, flights_len: int
) -> None:
    mock_set_up_accounts = mocker.patch("lib.main.set_up_accounts")
    mock_set_up_flights = mocker.patch("lib.main.set_up_flights")

    main.set_up_check_in(arguments)

    assert len(mock_set_up_accounts.call_args[0][0].accounts) == accounts_len
    assert len(mock_set_up_flights.call_args[0][0].flights) == flights_len


def test_set_up_check_in_sends_error_message_when_arguments_are_invalid(
    caplog: pytest.CaptureFixture[str],
) -> None:
    arguments = ["1", "2", "3", "4"]

    with pytest.raises(SystemExit):
        main.set_up_check_in(arguments)
    output = caplog.record_tuples[1]

    assert output[1] == logging.ERROR
    assert "Invalid arguments" in output[2]
    assert "--help" in output[2]


def test_main_sets_up_the_script(mocker: MockerFixture) -> None:
    mock_check_flags = mocker.patch("lib.main.check_flags")
    mock_init_logging = mocker.patch("lib.main.init_logging")
    mock_set_up_check_in = mocker.patch("lib.main.set_up_check_in")
    arguments = ["test", "arguments"]

    main.main(arguments)
    mock_check_flags.assert_called_once_with(arguments)
    mock_init_logging.assert_called_once()
    mock_set_up_check_in.assert_called_once_with(arguments)
