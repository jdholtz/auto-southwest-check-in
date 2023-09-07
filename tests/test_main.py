import logging
from typing import List

import pytest
from pytest_mock import MockerFixture

from lib import main
from lib.config import AccountConfig, GlobalConfig, ReservationConfig
from lib.notification_handler import NotificationHandler
from lib.reservation_monitor import AccountMonitor, ReservationMonitor


# We don't actually want the config to read the file for these tests
@pytest.fixture(autouse=True)
def mock_config(mocker: MockerFixture) -> None:
    mocker.patch("lib.config.GlobalConfig._read_config")


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


def test_get_notification_urls_gets_all_urls() -> None:
    config = GlobalConfig()
    config.accounts = [AccountConfig()]
    config.reservations = [ReservationConfig()]
    config.notification_urls = ["url1"]
    config.accounts[0].notification_urls = ["url1", "url2"]
    config.reservations[0].notification_urls = ["url1", "url3"]

    notification_urls = main.get_notification_urls(config)

    # Sort because order is not important
    assert sorted(notification_urls) == ["url1", "url2", "url3"]


def test_test_notifications_sends_to_every_url_in_config(mocker: MockerFixture) -> None:
    mock_send_notification = mocker.patch.object(NotificationHandler, "send_notification")

    config = GlobalConfig()
    main.test_notifications(config)
    mock_send_notification.assert_called_once()


def test_set_up_accounts_starts_all_accounts(mocker: MockerFixture) -> None:
    config = GlobalConfig()
    config.accounts = [AccountConfig(), AccountConfig()]

    mock_account_start = mocker.patch.object(AccountMonitor, "start")
    main.set_up_accounts(config, None)
    assert mock_account_start.call_count == len(config.accounts)


def test_set_up_reservations_starts_all_reservations(mocker: MockerFixture) -> None:
    config = GlobalConfig()
    config.reservations = [ReservationConfig(), ReservationConfig()]

    mock_reservation_start = mocker.patch.object(ReservationMonitor, "start")
    main.set_up_reservations(config, None)
    assert mock_reservation_start.call_count == len(config.reservations)


def test_set_up_check_in_sends_test_notifications_when_flag_passed(mocker: MockerFixture) -> None:
    mock_test_notifications = mocker.patch("lib.main.test_notifications")
    with pytest.raises(SystemExit):
        main.set_up_check_in(["--test-notifications"])
    mock_test_notifications.assert_called_once()


@pytest.mark.parametrize(
    ["arguments", "accounts_len", "reservations_len"],
    [
        ([], 0, 0),
        (["username", "password"], 1, 0),
        (["test", "John", "Doe"], 0, 1),
    ],
)
def test_set_up_check_in_sets_up_account_and_reservation_with_arguments(
    mocker: MockerFixture, arguments: List[str], accounts_len: int, reservations_len: int
) -> None:
    mock_process = mocker.patch("multiprocessing.Process")
    mock_processes = [mock_process] * (accounts_len + reservations_len)
    mocker.patch("multiprocessing.active_children", return_value=mock_processes)

    mock_set_up_accounts = mocker.patch("lib.main.set_up_accounts")
    mock_set_up_reservations = mocker.patch("lib.main.set_up_reservations")

    main.set_up_check_in(arguments)

    assert len(mock_set_up_accounts.call_args[0][0].accounts) == accounts_len
    assert len(mock_set_up_reservations.call_args[0][0].reservations) == reservations_len
    assert mock_process.join.call_count == len(mock_processes)


def test_set_up_check_in_sends_error_message_when_arguments_are_invalid(
    caplog: pytest.CaptureFixture[str],
) -> None:
    arguments = ["1", "2", "3", "4"]

    with pytest.raises(SystemExit):
        main.set_up_check_in(arguments)
    output = caplog.record_tuples[-1]

    assert output[1] == logging.ERROR
    assert "Invalid arguments" in output[2]
    assert "--help" in output[2]


def test_main_sets_up_the_script(mocker: MockerFixture) -> None:
    mock_check_flags = mocker.patch("lib.main.check_flags")
    mock_init_main_logging = mocker.patch("lib.log.init_main_logging")
    mock_set_up_check_in = mocker.patch("lib.main.set_up_check_in")
    arguments = ["test", "arguments", "--verbose", "-v"]

    main.main(arguments)
    mock_check_flags.assert_called_once_with(arguments)
    mock_init_main_logging.assert_called_once()

    # Ensure the '--verbose' and '-v' flags are removed
    mock_set_up_check_in.assert_called_once_with(arguments[:2])


def test_main_exits_on_keyboard_interrupt(mocker: MockerFixture) -> None:
    mocker.patch("lib.main.check_flags")
    mocker.patch("lib.log.init_main_logging")
    mocker.patch("lib.main.set_up_check_in", side_effect=KeyboardInterrupt)

    with pytest.raises(SystemExit):
        main.main([])
