from unittest import mock

import apprise
from pytest_mock import MockerFixture

from lib.account import Account
from lib.general import CheckInError, NotificationLevel
from lib.webdriver import WebDriver

# This needs to be accessed to be tested
# pylint: disable=protected-access


def test_get_flights_processes_retrieved_flights(mocker: MockerFixture) -> None:
    mocker.patch.object(
        WebDriver,
        "get_info",
        return_value=[{"confirmationNumber": "flight1"}, {"confirmationNumber": "flight2"}],
    )
    mock_get_reservation_info = mocker.patch.object(Account, "_get_reservation_info")
    mock_send_new_flight_notifications = mocker.patch.object(
        Account, "_send_new_flight_notifications"
    )

    test_account = Account()
    test_account.get_flights()

    mock_get_reservation_info.assert_has_calls([mock.call("flight1"), mock.call("flight2")])
    mock_send_new_flight_notifications.asseert_called_once_with(0)


def test_get_checkin_info_retrives_info_for_one_flight(mocker: MockerFixture) -> None:
    mock_refresh_headers = mocker.patch.object(Account, "refresh_headers")
    mock_get_reservation_info = mocker.patch.object(Account, "_get_reservation_info")
    mock_send_new_flight_notifications = mocker.patch.object(
        Account, "_send_new_flight_notifications"
    )

    test_account = Account()
    test_account.get_checkin_info("flight1")

    mock_refresh_headers.assert_called_once()
    mock_get_reservation_info.assert_called_once_with("flight1")
    mock_send_new_flight_notifications.assert_called_once_with(0)


def test_refresh_headers_sets_new_headers(mocker: MockerFixture) -> None:
    mocker.patch.object(WebDriver, "get_info", return_value={"test": "headers"})

    test_account = Account()
    test_account.refresh_headers()

    assert test_account.headers == {"test": "headers"}


def test_get_reservation_info_sends_error_notification_when_reservation_retrieval_fails(
    mocker: MockerFixture,
) -> None:
    mocker.patch("lib.account.make_request", side_effect=CheckInError())
    mock_send_notification = mocker.patch.object(Account, "send_notification")

    test_account = Account()
    test_account._get_reservation_info("flight1")

    assert mock_send_notification.call_args[0][1] == NotificationLevel.ERROR
    assert len(test_account.flights) == 0


def test_get_reservation_info_does_not_schedule_departed_flights(mocker: MockerFixture) -> None:
    flight_info = {"viewReservationViewPage": {"bounds": [{"departureStatus": "DEPARTED"}]}}
    mocker.patch("lib.account.make_request", return_value=flight_info)

    test_account = Account()
    test_account._get_reservation_info("flight1")

    assert len(test_account.flights) == 0


def test_get_reservation_info_schedules_all_flights_under_one_reservation(
    mocker: MockerFixture,
) -> None:
    flight_info = {
        "viewReservationViewPage": {
            "bounds": [{"departureStatus": "WAITING"}, {"departureStatus": "WAITING"}]
        }
    }
    mocker.patch("lib.account.make_request", return_value=flight_info)
    mock_flight = mocker.patch("lib.account.Flight")

    test_account = Account()
    test_account._get_reservation_info("flight1")

    assert len(test_account.flights) == 2
    assert mock_flight.call_count == 2


def test_send_new_flight_notifications_sends_no_notification_if_no_new_flights_are_scheduled(
    mocker: MockerFixture,
) -> None:
    mock_send_notification = mocker.patch.object(Account, "send_notification")

    test_account = Account()
    test_account._send_new_flight_notifications(0)

    mock_send_notification.assert_not_called()


def test_send_new_flight_notifications_sends_notifications_for_new_flights(
    mocker: MockerFixture,
) -> None:
    mock_send_notification = mocker.patch.object(Account, "send_notification")
    mock_flight = mocker.patch("lib.account.Flight")

    test_account = Account()
    test_account.flights.append(mock_flight)
    test_account._send_new_flight_notifications(0)

    assert mock_send_notification.call_args[0][1] == NotificationLevel.INFO


def test_send_notification_does_not_send_notifications_if_notication_config_is_empty(
    mocker: MockerFixture,
) -> None:
    mock_apprise_notify = mocker.patch.object(apprise.Apprise, "notify")
    test_account = Account()
    test_account.config.notification_urls = []  # Just in case it isn't empty

    test_account.send_notification("")

    mock_apprise_notify.assert_not_called()


def test_send_nofication_does_not_send_notifications_if_level_is_too_low(
    mocker: MockerFixture,
) -> None:
    mock_apprise_notify = mocker.patch.object(apprise.Apprise, "notify")
    test_account = Account()
    test_account.config.notification_urls = ["url"]
    test_account.config.notification_level = 2

    test_account.send_notification("", 1)

    mock_apprise_notify.assert_not_called()


def test_send_notification_sends_notifications_with_the_correct_content(
    mocker: MockerFixture,
) -> None:
    mock_apprise_notify = mocker.patch.object(apprise.Apprise, "notify")
    test_account = Account()
    test_account.config.notification_urls = ["url"]

    test_account.send_notification("test notification", 1)

    assert mock_apprise_notify.call_args[1]["body"] == "test notification"
