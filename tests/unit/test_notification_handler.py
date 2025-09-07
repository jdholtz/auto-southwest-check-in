import apprise
import pytest
from pytest_mock import MockerFixture

from lib.config import NotificationConfig
from lib.notification_handler import FLIGHT_TIME_PLACEHOLDER, NotificationHandler
from lib.utils import NotificationLevel


class TestNotificationHandler:
    def _get_notification_config(self) -> list[NotificationConfig]:
        notif1 = NotificationConfig()
        notif1.url = "http://test1"
        notif1.level = NotificationLevel.INFO
        notif2 = NotificationConfig()
        notif2.url = "http://test2"
        notif2.level = NotificationLevel.ERROR
        return [notif1, notif2]

    @pytest.fixture(autouse=True)
    def notification_handler(self, mocker: MockerFixture) -> None:
        mock_reservation_monitor = mocker.patch("lib.reservation_monitor.ReservationMonitor")
        self.handler = NotificationHandler(mock_reservation_monitor)

    def test_send_nofication_does_not_send_notifications_if_level_is_too_low(
        self, mocker: MockerFixture
    ) -> None:
        mock_apprise = mocker.patch.object(apprise.Apprise, "__init__", return_value=None)
        mock_apprise_notify = mocker.patch.object(apprise.Apprise, "notify")
        self.handler.notifications = self._get_notification_config()

        self.handler.send_notification("", NotificationLevel.INFO)

        mock_apprise.assert_called_once_with(self.handler.notifications[0].url)
        mock_apprise_notify.assert_called_once()

    @pytest.mark.parametrize("level", [NotificationLevel.ERROR, None])
    def test_send_notification_sends_notifications_with_the_correct_content(
        self, mocker: MockerFixture, level: NotificationLevel
    ) -> None:
        mock_apprise = mocker.patch.object(apprise.Apprise, "__init__", return_value=None)
        mock_apprise_notify = mocker.patch.object(apprise.Apprise, "notify")
        self.handler.notifications = self._get_notification_config()

        self.handler.send_notification("test notification", level)

        assert mock_apprise.call_count == 2
        assert mock_apprise.call_args_list == [
            mocker.call(self.handler.notifications[0].url),
            mocker.call(self.handler.notifications[1].url),
        ]

        assert mock_apprise_notify.call_count == 2
        assert mock_apprise_notify.call_args[1]["body"] == "test notification"

    def test_format_flight_times_replaces_all_flight_times(self, mocker: MockerFixture) -> None:
        mock_flight1 = mocker.patch("lib.flight.Flight")
        mock_flight1.get_display_time.return_value = "2021-01-01 00:00 UTC"
        mock_flight2 = mocker.patch("lib.flight.Flight")
        mock_flight2.get_display_time.return_value = "2021-01-01 01:00 UTC"

        body = (
            f"New flight scheduled at {FLIGHT_TIME_PLACEHOLDER} and another new flight scheduled "
            f"at {FLIGHT_TIME_PLACEHOLDER}"
        )
        formatted = self.handler._format_flight_times(body, [mock_flight1, mock_flight2], True)
        assert "2021-01-01 00:00 UTC" in formatted
        assert "2021-01-01 01:00 UTC" in formatted

    def test_new_flights_sends_no_notification_if_no_flights_exist(
        self, mocker: MockerFixture
    ) -> None:
        mock_send_notification = mocker.patch.object(NotificationHandler, "send_notification")
        self.handler.new_flights([])
        mock_send_notification.assert_not_called()

    def test_new_flights_sends_notifications_for_new_flights(self, mocker: MockerFixture) -> None:
        mock_send_notification = mocker.patch.object(NotificationHandler, "send_notification")
        mock_flight = mocker.patch("lib.flight.Flight")
        mock_flight.is_international = False

        self.handler.new_flights([mock_flight])
        assert mock_send_notification.call_args[0][1] == NotificationLevel.INFO

    def test_new_flights_sends_passport_information_when_flight_is_international(
        self, mocker: MockerFixture
    ) -> None:
        mock_send_notification = mocker.patch.object(NotificationHandler, "send_notification")
        mock_flight = mocker.patch("lib.flight.Flight")
        mock_flight.is_international = True

        self.handler.new_flights([mock_flight])
        assert "passport information" in mock_send_notification.call_args[0][0]

    def test_reaccommodated_flights_sends_no_notification_if_no_flights_are_reaccommodated(
        self, mocker: MockerFixture
    ) -> None:
        mock_send_notification = mocker.patch.object(NotificationHandler, "send_notification")
        self.handler.reaccommodated_flights([])
        mock_send_notification.assert_not_called()

    def test_reaccommodated_flights_sends_notifications_for_reaccommodated_flights(
        self, mocker: MockerFixture
    ) -> None:
        mock_send_notification = mocker.patch.object(NotificationHandler, "send_notification")
        mock_flight = mocker.patch("lib.flight.Flight")

        self.handler.reaccommodated_flights([mock_flight])
        assert mock_send_notification.call_args[0][1] == NotificationLevel.INFO

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

    def test_timeout_during_retrieval_sends_notice_notification(
        self, mocker: MockerFixture
    ) -> None:
        mock_send_notification = mocker.patch.object(NotificationHandler, "send_notification")
        self.handler.timeout_during_retrieval("test")
        assert mock_send_notification.call_args[0][1] == NotificationLevel.NOTICE

    def test_too_many_requests_during_login_sends_notice_notification(
        self, mocker: MockerFixture
    ) -> None:
        mock_send_notification = mocker.patch.object(NotificationHandler, "send_notification")
        self.handler.too_many_requests_during_login()
        assert mock_send_notification.call_args[0][1] == NotificationLevel.NOTICE

    def test_successful_checkin_sends_notification_for_check_in(
        self, mocker: MockerFixture
    ) -> None:
        mock_send_notification = mocker.patch.object(NotificationHandler, "send_notification")
        mock_flight = mocker.patch("lib.flight.Flight")

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
        assert mock_send_notification.call_args[0][1] == NotificationLevel.CHECKIN

    def test_successful_checkin_does_not_include_notification_for_lap_child(
        self, mocker: MockerFixture
    ) -> None:
        """
        A lap child does not get a boarding position, and does not need a notification
        """
        mock_send_notification = mocker.patch.object(NotificationHandler, "send_notification")
        mock_flight = mocker.patch("lib.flight.Flight")

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
        assert "Lap Child" not in mock_send_notification.call_args[0][0]
        assert mock_send_notification.call_args[0][1] == NotificationLevel.CHECKIN

    def test_failed_checkin_sends_error_notification(self, mocker: MockerFixture) -> None:
        mock_send_notification = mocker.patch.object(NotificationHandler, "send_notification")
        mock_flight = mocker.patch("lib.flight.Flight")

        self.handler.failed_checkin("", mock_flight)
        assert mock_send_notification.call_args[0][1] == NotificationLevel.ERROR

    def test_airport_checkin_required_sends_error_notification(self, mocker: MockerFixture) -> None:
        mock_send_notification = mocker.patch.object(NotificationHandler, "send_notification")
        mock_flight = mocker.patch("lib.flight.Flight")

        self.handler.airport_checkin_required(mock_flight)
        assert mock_send_notification.call_args[0][1] == NotificationLevel.ERROR

    def test_timeout_before_checkin_sends_error_notification(self, mocker: MockerFixture) -> None:
        mock_send_notification = mocker.patch.object(NotificationHandler, "send_notification")
        mock_flight = mocker.patch("lib.flight.Flight")

        self.handler.timeout_before_checkin(mock_flight)
        assert mock_send_notification.call_args[0][1] == NotificationLevel.ERROR

    def test_lower_fare_sends_lower_fare_notification(self, mocker: MockerFixture) -> None:
        mock_send_notification = mocker.patch.object(NotificationHandler, "send_notification")
        mock_flight = mocker.patch("lib.flight.Flight")

        self.handler.lower_fare(mock_flight, "")
        assert mock_send_notification.call_args[0][1] == NotificationLevel.INFO

    @pytest.mark.parametrize(("url", "expected_calls"), [("http://healthchecks", 1), (None, 0)])
    def test_healthchecks_success_pings_url_only_if_configured(
        self, mocker: MockerFixture, url: str, expected_calls: int
    ) -> None:
        mock_post = mocker.patch("requests.post")
        self.handler.reservation_monitor.config.healthchecks_url = url

        self.handler.healthchecks_success("healthchecks success")
        assert mock_post.call_count == expected_calls

    @pytest.mark.parametrize(("url", "expected_calls"), [("http://healthchecks", 1), (None, 0)])
    def test_healthchecks_fail_pings_url_only_if_configured(
        self, mocker: MockerFixture, url: str, expected_calls: int
    ) -> None:
        mock_post = mocker.patch("requests.post")
        self.handler.reservation_monitor.config.healthchecks_url = url

        self.handler.healthchecks_fail("healthchecks fail")
        assert mock_post.call_count == expected_calls

    def test_get_account_name_returns_the_reservation_monitor_name(self) -> None:
        self.handler.reservation_monitor.get_account_name.return_value = "John Doe"
        assert self.handler._get_account_name() == "John Doe"
