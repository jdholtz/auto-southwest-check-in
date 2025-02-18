import logging

import pytest
from pytest_mock import MockerFixture
from requests_mock.mocker import Mocker as RequestMocker

from lib import main
from lib.config import AccountConfig, GlobalConfig, ReservationConfig
from lib.notification_handler import NotificationHandler
from lib.reservation_monitor import AccountMonitor, ReservationMonitor


@pytest.fixture(autouse=True)
def mock_config(mocker: MockerFixture) -> None:
    """The config file shouldn't actually be read for these tests"""
    mocker.patch("lib.config.GlobalConfig._read_config")


def test_get_timezone_fetches_timezone_from_request(requests_mock: RequestMocker) -> None:
    requests_mock.get(main.IP_TIMEZONE_URL, text="Asia/Tokyo")
    assert main.get_timezone() == "Asia/Tokyo"


def test_get_timezone_returns_utc_when_request_fails(requests_mock: RequestMocker) -> None:
    requests_mock.get(main.IP_TIMEZONE_URL, status_code=500)
    assert main.get_timezone() == "UTC"


def test_test_notifications_sends_to_every_url_in_config(mocker: MockerFixture) -> None:
    # pylint: disable=protected-access
    # Accessing protected methods is just used to not need to provide a full config object
    # to parse

    config = GlobalConfig()
    config.accounts = [AccountConfig()]
    config.reservations = [ReservationConfig()]
    config._create_notification_config([{"url": "url1"}])

    config.accounts[0]._create_notification_config([{"url": "url1"}])
    config.accounts[0]._create_notification_config([{"url": "url2"}])

    config.reservations[0]._create_notification_config([{"url": "url3"}])
    config.reservations[0]._create_notification_config([{"url": "url1"}])

    mock_send_notification = mocker.patch.object(NotificationHandler, "send_notification")

    main.test_notifications(config)

    # Make sure the configs were merged correctly so all of the URLs are only sent one test
    # notification each
    assert len(config.notifications) == 3

    mock_send_notification.assert_called_once()


@pytest.mark.parametrize(["expected", "count"], [("tests", 0), ("test", 1), ("tests", 2)])
def test_pluralize_pluralizes_a_word_if_needed(expected: str, count: int) -> None:
    assert main.pluralize("test", count) == expected


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
    mocker: MockerFixture, arguments: list[str], accounts_len: int, reservations_len: int
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
    mock_init_main_logging = mocker.patch("lib.log.init_main_logging")
    mock_set_up_check_in = mocker.patch("lib.main.set_up_check_in")
    mock_get_timezone = mocker.patch("lib.main.get_timezone")

    arguments = ["test", "arguments", "--verbose", "-v"]
    main.main(arguments, "test_version")
    mock_init_main_logging.assert_called_once()

    # Ensure the '--verbose' and '-v' flags are removed
    mock_set_up_check_in.assert_called_once_with(arguments[:2])

    mock_get_timezone.assert_not_called()


def test_main_fetches_timezone_if_docker(mocker: MockerFixture) -> None:
    mocker.patch("lib.log.init_main_logging")
    mocker.patch("lib.main.set_up_check_in")

    mock_get_timezone = mocker.patch("lib.main.get_timezone", return_value="UTC")
    mocker.patch("lib.main.IS_DOCKER", return_value=True)

    main.main([], "test_version")
    mock_get_timezone.assert_called_once()


def test_main_exits_on_keyboard_interrupt(mocker: MockerFixture) -> None:
    mocker.patch("lib.log.init_main_logging")
    mocker.patch.object(main, "set_up_check_in", side_effect=KeyboardInterrupt)

    with pytest.raises(SystemExit):
        main.main([], "test_version")
