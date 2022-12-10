import apprise
import pytest
from pytest_mock import MockerFixture

from lib.flight_retriever import FlightRetriever
from lib.general import NotificationLevel
from lib.notification_handler import NotificationHandler

# This needs to be accessed to be tested
# pylint: disable=protected-access


@pytest.fixture
def notification_handler() -> NotificationHandler:
    return NotificationHandler(FlightRetriever())


def test_get_account_name_returns_the_correct_name(
    notification_handler: NotificationHandler,
) -> None:
    notification_handler.flight_retriever.first_name = "John"
    notification_handler.flight_retriever.last_name = "Doe"

    assert notification_handler._get_account_name() == "John Doe"


def test_send_nofication_does_not_send_notifications_if_level_is_too_low(
    mocker: MockerFixture, notification_handler: NotificationHandler
) -> None:
    mock_apprise_notify = mocker.patch.object(apprise.Apprise, "notify")
    notification_handler.notification_level = 2

    notification_handler.send_notification("", 1)

    mock_apprise_notify.assert_not_called()


@pytest.mark.parametrize("level", [2, None])
def test_send_notification_sends_notifications_with_the_correct_content(
    mocker: MockerFixture, notification_handler: NotificationHandler, level: int
) -> None:
    mock_apprise_notify = mocker.patch.object(apprise.Apprise, "notify")
    notification_handler.notification_urls = ["url"]
    notification_handler.notification_level = 1

    notification_handler.send_notification("test notification", level)

    assert mock_apprise_notify.call_args[1]["body"] == "test notification"


def test_new_flights_sends_no_notification_if_no_flights_exist(
    mocker: MockerFixture, notification_handler: NotificationHandler
) -> None:
    mock_send_notification = mocker.patch.object(NotificationHandler, "send_notification")

    notification_handler.new_flights([])

    mock_send_notification.assert_not_called()


def test_new_flights_sends_notifications_for_new_flights(
    mocker: MockerFixture, notification_handler: NotificationHandler
) -> None:
    mock_send_notification = mocker.patch.object(NotificationHandler, "send_notification")
    mock_flight = mocker.patch("lib.notification_handler.Flight")

    notification_handler.new_flights([mock_flight])

    assert mock_send_notification.call_args[0][1] == NotificationLevel.INFO


def test_failed_retrieval_reservation_sends_error_notification(
    mocker: MockerFixture, notification_handler: NotificationHandler
) -> None:
    mock_send_notification = mocker.patch.object(NotificationHandler, "send_notification")
    notification_handler.failed_reservation_retrieval("", "")
    assert mock_send_notification.call_args[0][1] == NotificationLevel.ERROR


def test_successful_checkin_sends_notification_for_check_in(
    mocker: MockerFixture, notification_handler: NotificationHandler
) -> None:
    mock_send_notification = mocker.patch.object(NotificationHandler, "send_notification")
    mock_flight = mocker.patch("lib.notification_handler.Flight")

    notification_handler.successful_checkin(
        {
            "flights": [
                {"passengers": [{"name": "John", "boardingGroup": "A", "boardingPosition": "1"}]}
            ]
        },
        mock_flight,
    )
    assert mock_send_notification.call_args[0][1] == NotificationLevel.INFO


def test_failed_checkin_sends_error_notification(
    mocker: MockerFixture, notification_handler: NotificationHandler
) -> None:
    mock_send_notification = mocker.patch.object(NotificationHandler, "send_notification")
    mock_flight = mocker.patch("lib.notification_handler.Flight")

    notification_handler.failed_checkin("", mock_flight)
    assert mock_send_notification.call_args[0][1] == NotificationLevel.ERROR
