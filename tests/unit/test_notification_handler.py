import apprise
import pytest
from pytest_mock import MockerFixture

from lib.notification_handler import NotificationHandler
from lib.utils import NotificationLevel

# This needs to be accessed to be tested
# pylint: disable=protected-access


class TestNotificationHandler:
    @pytest.fixture(autouse=True)
    def notification_handler(self, mocker: MockerFixture) -> None:
        mock_reservation_monitor = mocker.patch("lib.reservation_monitor.ReservationMonitor")
        # pylint: disable=attribute-defined-outside-init
        self.handler = NotificationHandler(mock_reservation_monitor)

    def test_send_nofication_does_not_send_notifications_if_level_is_too_low(
        self, mocker: MockerFixture
    ) -> None:
        mock_apprise_notify = mocker.patch.object(apprise.Apprise, "notify")
        self.handler.notification_level = 2

        self.handler.send_notification("", 1)
        mock_apprise_notify.assert_not_called()

    @pytest.mark.parametrize("level", [2, None])
    def test_send_notification_sends_notifications_with_the_correct_content(
        self, mocker: MockerFixture, level: int
    ) -> None:
        mock_apprise_notify = mocker.patch.object(apprise.Apprise, "notify")
        self.handler.notification_urls = ["url"]
        self.handler.notification_level = 1

        self.handler.send_notification("test notification", level)
        assert mock_apprise_notify.call_args[1]["body"] == "test notification"

    def test_new_flights_sends_no_notification_if_no_flights_exist(
        self, mocker: MockerFixture
    ) -> None:
        mock_send_notification = mocker.patch.object(NotificationHandler, "send_notification")
        self.handler.new_flights([])
        mock_send_notification.assert_not_called()

    def test_new_flights_sends_notifications_for_new_flights(self, mocker: MockerFixture) -> None:
        mock_send_notification = mocker.patch.object(NotificationHandler, "send_notification")
        mock_flight = mocker.patch("lib.notification_handler.Flight")
        mock_flight.is_international = False

        self.handler.new_flights([mock_flight])
        assert mock_send_notification.call_args[0][1] == NotificationLevel.INFO

    def test_new_flights_sends_passport_information_when_flight_is_international(
        self, mocker: MockerFixture
    ) -> None:
        mock_send_notification = mocker.patch.object(NotificationHandler, "send_notification")
        mock_flight = mocker.patch("lib.notification_handler.Flight")
        mock_flight.is_international = True

        self.handler.new_flights([mock_flight])
        assert "passport information" in mock_send_notification.call_args[0][0]

    def test_failed_reservation_retrieval_sends_error_notification(
        self, mocker: MockerFixture
    ) -> None:
        mock_send_notification = mocker.patch.object(NotificationHandler, "send_notification")
        self.handler.failed_reservation_retrieval("", "")
        assert mock_send_notification.call_args[0][1] == NotificationLevel.ERROR

    def test_failed_login_sends_error_notification(self, mocker: MockerFixture) -> None:
        mock_send_notification = mocker.patch.object(NotificationHandler, "send_notification")
        self.handler.failed_login("")
        assert mock_send_notification.call_args[0][1] == NotificationLevel.ERROR

    def test_successful_checkin_sends_notification_for_check_in(
        self, mocker: MockerFixture
    ) -> None:
        mock_send_notification = mocker.patch.object(NotificationHandler, "send_notification")
        mock_flight = mocker.patch("lib.notification_handler.Flight")

        self.handler.successful_checkin(
            {
                "flights": [
                    {
                        "passengers": [
                            {"name": "John", "boardingGroup": "A", "boardingPosition": "1"}
                        ]
                    }
                ]
            },
            mock_flight,
        )
        assert mock_send_notification.call_args[0][1] == NotificationLevel.INFO

    def test_does_not_include_notification_for_lap_child(self, mocker: MockerFixture) -> None:
        """
        A lap child does not get a boarding position, and does not need a notification
        """
        mock_send_notification = mocker.patch.object(NotificationHandler, "send_notification")
        mock_flight = mocker.patch("lib.notification_handler.Flight")

        self.handler.successful_checkin(
            {
                "flights": [
                    {
                        "passengers": [
                            {"name": "John", "boardingGroup": "A", "boardingPosition": "1"},
                            {"name": "Lap Child", "boardingGroup": None, "boardingPosition": None},
                        ]
                    }
                ]
            },
            mock_flight,
        )
        assert "John got A1!" in mock_send_notification.call_args[0][0]
        assert "Lap Child got NoneNone!" not in mock_send_notification.call_args[0][0]
        assert mock_send_notification.call_args[0][1] == NotificationLevel.INFO

    def test_failed_checkin_sends_error_notification(self, mocker: MockerFixture) -> None:
        mock_send_notification = mocker.patch.object(NotificationHandler, "send_notification")
        mock_flight = mocker.patch("lib.notification_handler.Flight")

        self.handler.failed_checkin("", mock_flight)
        assert mock_send_notification.call_args[0][1] == NotificationLevel.ERROR

    def test_lower_fare_sends_lower_fare_notification(self, mocker: MockerFixture) -> None:
        mock_send_notification = mocker.patch.object(NotificationHandler, "send_notification")
        mock_flight = mocker.patch("lib.notification_handler.Flight")

        self.handler.lower_fare(mock_flight, "")
        assert mock_send_notification.call_args[0][1] == NotificationLevel.INFO

    def test_get_account_name_returns_the_correct_name(self) -> None:
        self.handler.reservation_monitor.first_name = "John"
        self.handler.reservation_monitor.last_name = "Doe"
        assert self.handler._get_account_name() == "John Doe"
