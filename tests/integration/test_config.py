"""Tests the config module to ensure global and local configuration values are respected"""

import json

from pytest_mock import MockerFixture

from lib.config import GlobalConfig, NotificationConfig
from lib.utils import CheckFaresOption, NotificationLevel


def assert_notification_config_matches(
    notification_config: NotificationConfig,
    expected_url: str,
    expected_level: NotificationLevel,
    expected_24_hr_time: bool,
) -> None:
    assert notification_config.url == expected_url
    assert notification_config.level == expected_level
    assert notification_config.twenty_four_hour_time is expected_24_hr_time


def test_config(mocker: MockerFixture) -> None:
    config = {
        "browser_path": "chrome_path",
        "check_fares": CheckFaresOption.SAME_DAY_NONSTOP,
        "notifications": [{"url": "test1.com", "level": 1}, {"url": "test2.com"}],
        "retrieval_interval": 16,
        "accounts": [
            {"username": "test_user1", "password": "test_pass1"},
            {
                "username": "test_user2",
                "password": "test_pass2",
                "check_fares": False,
                "notifications": [{"url": "test1.com", "level": 3}, {"url": "test3.com"}],
                "retrieval_interval": 10,
            },
        ],
        "reservations": [
            {"confirmationNumber": "test_num1", "firstName": "Winston", "lastName": "Smith"},
            {
                "confirmationNumber": "test_num2",
                "firstName": "Edmond",
                "lastName": "Dantès",
                "check_fares": False,
                "notifications": [{"url": "test4.com", "24_hour_time": True}],
                "retrieval_interval": 8,
            },
        ],
    }

    mocker.patch("pathlib.Path.read_text", return_value=json.dumps(config))

    config = GlobalConfig()
    config.initialize()

    assert len(config.accounts) == 2
    assert len(config.reservations) == 2

    # Check the account configurations
    account_one = config.accounts[0]
    account_two = config.accounts[1]

    assert account_one.browser_path == "chrome_path"
    assert account_one.check_fares == CheckFaresOption.SAME_DAY_NONSTOP
    assert account_one.retrieval_interval == 16 * 3600
    assert account_one.username == "test_user1"
    assert account_one.password == "test_pass1"

    assert len(account_one.notifications) == 2
    assert_notification_config_matches(
        account_one.notifications[0], "test1.com", NotificationLevel.NOTICE, False
    )
    assert_notification_config_matches(
        account_one.notifications[1], "test2.com", NotificationLevel.INFO, False
    )

    assert account_two.browser_path == "chrome_path"
    assert account_two.check_fares == CheckFaresOption.NO
    assert account_two.retrieval_interval == 10 * 3600
    assert account_two.username == "test_user2"
    assert account_two.password == "test_pass2"

    assert len(account_two.notifications) == 3
    assert_notification_config_matches(
        account_two.notifications[0], "test1.com", NotificationLevel.CHECKIN, False
    )
    assert_notification_config_matches(
        account_two.notifications[1], "test3.com", NotificationLevel.INFO, False
    )
    assert_notification_config_matches(
        account_two.notifications[2], "test2.com", NotificationLevel.INFO, False
    )

    # Check the reservation configurations
    reservation_one = config.reservations[0]
    reservation_two = config.reservations[1]

    assert reservation_one.browser_path == "chrome_path"
    assert reservation_one.check_fares == CheckFaresOption.SAME_DAY_NONSTOP
    assert reservation_one.confirmation_number == "test_num1"
    assert reservation_one.first_name == "Winston"
    assert reservation_one.last_name == "Smith"
    assert reservation_one.retrieval_interval == 16 * 3600

    assert len(reservation_one.notifications) == 2
    assert_notification_config_matches(
        reservation_one.notifications[0], "test1.com", NotificationLevel.NOTICE, False
    )
    assert_notification_config_matches(
        reservation_one.notifications[1], "test2.com", NotificationLevel.INFO, False
    )

    assert reservation_two.browser_path == "chrome_path"
    assert reservation_two.check_fares == CheckFaresOption.NO
    assert reservation_two.confirmation_number == "test_num2"
    assert reservation_two.first_name == "Edmond"
    assert reservation_two.last_name == "Dantès"
    assert reservation_two.retrieval_interval == 8 * 3600

    assert len(reservation_two.notifications) == 3
    assert_notification_config_matches(
        reservation_two.notifications[0], "test4.com", NotificationLevel.INFO, True
    )
    assert_notification_config_matches(
        reservation_two.notifications[1], "test1.com", NotificationLevel.NOTICE, False
    )
    assert_notification_config_matches(
        reservation_two.notifications[2], "test2.com", NotificationLevel.INFO, False
    )
