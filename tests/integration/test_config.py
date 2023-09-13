"""Tests the config module to ensure global and local configuration values are respected"""

import json

from pytest_mock import MockerFixture

from lib.config import GlobalConfig


def test_config(mocker: MockerFixture) -> None:
    config = {
        "browser_path": "chrome_path",
        "check_fares": True,
        "chrome_version": 10,
        "chromedriver_path": "driver_path",
        "notification_level": 1,
        "notification_urls": ["test1.com", "test2.com"],
        "retrieval_interval": 16,
        "accounts": [
            {"username": "test_user1", "password": "test_pass1"},
            {
                "username": "test_user2",
                "password": "test_pass2",
                "check_fares": False,
                "notification_level": 2,
                "notification_urls": "test3.com",
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
                "notification_level": 2,
                "notification_urls": "test4.com",
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
    assert account_one.check_fares
    assert account_one.chrome_version == 10
    assert account_one.chromedriver_path == "driver_path"
    assert account_one.notification_level == 1
    assert account_one.notification_urls == ["test1.com", "test2.com"]
    assert account_one.password == "test_pass1"
    assert account_one.retrieval_interval == 16 * 3600
    assert account_one.username == "test_user1"

    assert account_two.browser_path == "chrome_path"
    assert not account_two.check_fares
    assert account_two.chrome_version == 10
    assert account_two.chromedriver_path == "driver_path"
    assert account_two.notification_level == 2
    assert account_two.notification_urls == ["test1.com", "test2.com", "test3.com"]
    assert account_two.password == "test_pass2"
    assert account_two.retrieval_interval == 10 * 3600
    assert account_two.username == "test_user2"

    # Check the reservation configurations
    reservation_one = config.reservations[0]
    reservation_two = config.reservations[1]

    assert reservation_one.browser_path == "chrome_path"
    assert reservation_one.check_fares
    assert reservation_one.chrome_version == 10
    assert reservation_one.chromedriver_path == "driver_path"
    assert reservation_one.confirmation_number == "test_num1"
    assert reservation_one.first_name == "Winston"
    assert reservation_one.last_name == "Smith"
    assert reservation_one.notification_level == 1
    assert reservation_one.notification_urls == ["test1.com", "test2.com"]
    assert reservation_one.retrieval_interval == 16 * 3600

    assert reservation_two.browser_path == "chrome_path"
    assert not reservation_two.check_fares
    assert reservation_two.chrome_version == 10
    assert reservation_two.chromedriver_path == "driver_path"
    assert reservation_two.confirmation_number == "test_num2"
    assert reservation_two.first_name == "Edmond"
    assert reservation_two.last_name == "Dantès"
    assert reservation_two.notification_level == 2
    assert reservation_two.notification_urls == ["test1.com", "test2.com", "test4.com"]
    assert reservation_two.retrieval_interval == 8 * 3600
