import json
from pathlib import Path
from typing import Any, Dict, List, Union

import pytest
from pytest_mock import MockerFixture

from lib.config import AccountConfig, Config, ConfigError, GlobalConfig, ReservationConfig
from lib.utils import NotificationLevel

JSON = Dict[str, Any]

# This needs to be accessed to be tested
# pylint: disable=protected-access


class TestConfig:
    def test_create_merges_and_parses_config(self, mocker: MockerFixture) -> None:
        mock_merge_globals = mocker.patch.object(Config, "_merge_globals")
        mock_parse_config = mocker.patch.object(Config, "_parse_config")

        global_config = GlobalConfig()
        test_config = Config()
        test_config.create({"test": "config"}, global_config)

        mock_merge_globals.assert_called_once_with(global_config)
        mock_parse_config.assert_called_once_with({"test": "config"})

    def test_merge_globals_merges_all_global_config_options(self) -> None:
        global_config = GlobalConfig()
        test_config = Config()

        global_config._parse_config(
            {
                "browser_path": "test/browser_path",
                "check_fares": True,
                "healthchecks_url": "global_healthchecks",
                "notification_level": 1,
                "notification_urls": "url1",
                "retrieval_interval": 20,
            }
        )

        test_config._parse_config(
            {
                "browser_path": "test/browser_path2",
                "check_fares": False,
                "healthchecks_url": "test_healthchecks",
                "notification_level": 2,
                "notification_urls": ["url2"],
                "retrieval_interval": 10,
            }
        )

        test_config._merge_globals(global_config)

        assert test_config.check_fares == global_config.check_fares
        assert test_config.notification_level == global_config.notification_level
        assert test_config.notification_urls == ["url2", "url1"]
        assert test_config.retrieval_interval == global_config.retrieval_interval

        # Ensure only global configs are merged, not account/reservation-specific configs
        assert test_config.healthchecks_url == "test_healthchecks"

    @pytest.mark.parametrize(
        "config_content",
        [
            {"check_fares": "invalid"},
            {"healthchecks_url": 0},
            {"notification_level": "invalid"},
            {"notification_level": 3},
            {"notification_urls": None},
            {"retrieval_interval": "invalid"},
        ],
    )
    def test_parse_config_raises_exception_with_invalid_entries(self, config_content: JSON) -> None:
        test_config = Config()

        with pytest.raises(ConfigError):
            test_config._parse_config(config_content)

    def test_parse_config_sets_the_correct_config_values(self) -> None:
        test_config = Config()
        test_config._parse_config(
            {
                "check_fares": False,
                "healthchecks_url": "test_healthchecks",
                "notification_level": 2,
                "notification_urls": "test_url",
                "retrieval_interval": 30,
            }
        )

        assert test_config.check_fares is False
        assert test_config.healthchecks_url == "test_healthchecks"
        assert test_config.notification_level == NotificationLevel.ERROR
        assert test_config.notification_urls == ["test_url"]
        assert test_config.retrieval_interval == 30 * 60 * 60

    def test_parse_config_does_not_set_values_when_a_config_value_is_empty(self) -> None:
        test_config = Config()
        expected_config = Config()

        test_config._parse_config({})

        assert test_config.check_fares == expected_config.check_fares
        assert test_config.healthchecks_url == expected_config.healthchecks_url
        assert test_config.notification_urls == expected_config.notification_urls
        assert test_config.notification_level == expected_config.notification_level
        assert test_config.retrieval_interval == expected_config.retrieval_interval

    @pytest.mark.parametrize(
        ["notification_urls", "expected_urls"],
        [(["test_url"], ["test_url"]), ("test_url", ["test_url"]), ("", [])],
    )
    def test_parse_config_sets_the_correct_notification_urls(
        self, notification_urls: Union[List[str], str], expected_urls: [List[str]]
    ) -> None:
        test_config = Config()
        test_config._parse_config({"notification_urls": notification_urls})
        assert test_config.notification_urls == expected_urls

    def test_parse_config_sets_retrieval_interval_to_a_minimum(self) -> None:
        test_config = Config()
        test_config._parse_config({"retrieval_interval": -1})

        assert test_config.retrieval_interval == 0


class TestGlobalConfig:
    def test_initialize_reads_and_parses_config(self, mocker: MockerFixture) -> None:
        mock_read_config = mocker.patch.object(GlobalConfig, "_read_config")
        mock_parse_config = mocker.patch.object(GlobalConfig, "_parse_config")

        config = GlobalConfig()
        config.initialize()

        mock_read_config.assert_called_once()
        mock_parse_config.assert_called_once()

    @pytest.mark.parametrize(
        "exception", [ConfigError(), json.decoder.JSONDecodeError(None, "", 0)]
    )
    def test_config_exits_on_error_in_config_file(
        self, mocker: MockerFixture, exception: Exception
    ) -> None:
        mocker.patch.object(GlobalConfig, "_read_config", side_effect=exception)

        config = GlobalConfig()
        with pytest.raises(SystemExit):
            config.initialize()

    def test_create_account_config_creates_all_configs(self, mocker: MockerFixture) -> None:
        mock_config_create = mocker.patch.object(AccountConfig, "create")
        test_config = GlobalConfig()
        test_config.create_account_config([{"account": "one"}, {"account": "two"}])
        assert mock_config_create.call_count == 2

    def test_create_reservation_config_creates_all_configs(self, mocker: MockerFixture) -> None:
        mock_config_create = mocker.patch.object(ReservationConfig, "create")
        test_config = GlobalConfig()
        test_config.create_reservation_config([{"reservation": "one"}, {"reservation": "two"}])
        assert mock_config_create.call_count == 2

    def test_read_config_reads_the_config_file_correctly(self, mocker: MockerFixture) -> None:
        mocker.patch.object(Path, "read_text")
        mocker.patch("json.loads", return_value={"test": "data"})

        test_config = GlobalConfig()
        config_content = test_config._read_config()

        assert config_content == {"test": "data"}

    def test_read_config_returns_empty_config_when_file_not_found(
        self, mocker: MockerFixture
    ) -> None:
        mocker.patch.object(Path, "read_text", side_effect=FileNotFoundError())

        test_config = GlobalConfig()
        config_content = test_config._read_config()

        assert not config_content

    def test_read_config_raises_exception_when_config_not_dict(self, mocker: MockerFixture) -> None:
        mocker.patch.object(Path, "read_text")
        mocker.patch("json.loads", return_value="test")

        test_config = GlobalConfig()
        with pytest.raises(ConfigError):
            test_config._read_config()

    def test_read_env_vars_check_fares_successful(self, mocker: MockerFixture) -> None:
        mocker.patch.dict("os.environ", {"AUTO_SOUTHWEST_CHECK_IN_CHECK_FARES": "true"})
        test_config = GlobalConfig()
        config_content = test_config._read_env_vars({})

        assert config_content == {"check_fares": True}

    def test_read_env_vars_check_fares_override_json_config(self, mocker: MockerFixture) -> None:
        mocker.patch.dict("os.environ", {"AUTO_SOUTHWEST_CHECK_IN_CHECK_FARES": "true"})
        test_config = GlobalConfig()
        base_config = {"check_fares": False}
        config_content = test_config._read_env_vars(base_config)

        assert config_content == {"check_fares": True}

    def test_read_env_vars_check_fares_invalid(self, mocker: MockerFixture) -> None:
        mocker.patch.dict("os.environ", {"AUTO_SOUTHWEST_CHECK_IN_CHECK_FARES": "invalid"})
        test_config = GlobalConfig()
        with pytest.raises(ConfigError):
            test_config._read_env_vars({})

    def test_read_env_vars_notification_url_successful(self, mocker: MockerFixture) -> None:
        mocker.patch.dict("os.environ", {"AUTO_SOUTHWEST_CHECK_IN_NOTIFICATION_URL": "test_url"})
        test_config = GlobalConfig()
        config_content = test_config._read_env_vars({})

        assert config_content == {"notification_urls": ["test_url"]}

    def test_read_env_vars_notification_url_duplicate(self, mocker: MockerFixture) -> None:
        mocker.patch.dict("os.environ", {"AUTO_SOUTHWEST_CHECK_IN_NOTIFICATION_URL": "test_url"})
        test_config = GlobalConfig()
        base_config = {"notification_urls": ["test_url"]}
        config_content = test_config._read_env_vars(base_config)

        assert config_content == {"notification_urls": ["test_url"]}

    def test_read_env_vars_notification_url_additional(self, mocker: MockerFixture) -> None:
        mocker.patch.dict("os.environ", {"AUTO_SOUTHWEST_CHECK_IN_NOTIFICATION_URL": "test_url2"})
        test_config = GlobalConfig()
        base_config = {"notification_urls": ["test_url1"]}
        config_content = test_config._read_env_vars(base_config)

        assert config_content == {"notification_urls": ["test_url1", "test_url2"]}

    def test_read_env_vars_notification_url_base_string(self, mocker: MockerFixture) -> None:
        mocker.patch.dict("os.environ", {"AUTO_SOUTHWEST_CHECK_IN_NOTIFICATION_URL": "test_url2"})
        test_config = GlobalConfig()
        base_config = {"notification_urls": "test_url"}
        config_content = test_config._read_env_vars(base_config)

        assert config_content == {"notification_urls": ["test_url", "test_url2"]}

    def test_read_env_vars_notification_url_base_invalid(self, mocker: MockerFixture) -> None:
        mocker.patch.dict("os.environ", {"AUTO_SOUTHWEST_CHECK_IN_NOTIFICATION_URL": "test_url2"})
        test_config = GlobalConfig()
        base_config = {"notification_urls": 0}
        with pytest.raises(ConfigError):
            test_config._read_env_vars(base_config)

    def test_read_env_vars_notification_level_successful(self, mocker: MockerFixture) -> None:
        mocker.patch.dict("os.environ", {"AUTO_SOUTHWEST_CHECK_IN_NOTIFICATION_LEVEL": "1"})
        test_config = GlobalConfig()
        config_content = test_config._read_env_vars({})

        assert config_content == {"notification_level": 1}

    def test_read_env_vars_notification_level_invalid(self, mocker: MockerFixture) -> None:
        mocker.patch.dict("os.environ", {"AUTO_SOUTHWEST_CHECK_IN_NOTIFICATION_LEVEL": "invalid"})
        test_config = GlobalConfig()
        with pytest.raises(ConfigError):
            test_config._read_env_vars({})

    def test_read_env_vars_browser_path_successful(self, mocker: MockerFixture) -> None:
        mocker.patch.dict("os.environ", {"AUTO_SOUTHWEST_CHECK_IN_BROWSER_PATH": "test_path"})
        test_config = GlobalConfig()
        config_content = test_config._read_env_vars({})

        assert config_content == {"browser_path": "test_path"}

    def test_read_env_vars_browser_path_override_json_config(self, mocker: MockerFixture) -> None:
        mocker.patch.dict("os.environ", {"AUTO_SOUTHWEST_CHECK_IN_BROWSER_PATH": "test_path"})
        test_config = GlobalConfig()
        base_config = {"browser_path": "test_path2"}
        config_content = test_config._read_env_vars(base_config)

        assert config_content == {"browser_path": "test_path"}

    def test_read_env_vars_retrieval_interval_successful(self, mocker: MockerFixture) -> None:
        mocker.patch.dict("os.environ", {"AUTO_SOUTHWEST_CHECK_IN_RETRIEVAL_INTERVAL": "10"})
        test_config = GlobalConfig()
        config_content = test_config._read_env_vars({})

        assert config_content == {"retrieval_interval": 10}

    def test_read_env_vars_retrieval_interval_override_json_config(
        self, mocker: MockerFixture
    ) -> None:
        mocker.patch.dict("os.environ", {"AUTO_SOUTHWEST_CHECK_IN_RETRIEVAL_INTERVAL": "10"})
        test_config = GlobalConfig()
        base_config = {"retrieval_interval": 20}
        config_content = test_config._read_env_vars(base_config)

        assert config_content == {"retrieval_interval": 10}

    def test_read_env_vars_retrieval_interval_invalid(self, mocker: MockerFixture) -> None:
        mocker.patch.dict("os.environ", {"AUTO_SOUTHWEST_CHECK_IN_RETRIEVAL_INTERVAL": "invalid"})
        test_config = GlobalConfig()
        with pytest.raises(ConfigError):
            test_config._read_env_vars({})

    def test_read_env_vars_account_successful(self, mocker: MockerFixture) -> None:
        mocker.patch.dict("os.environ", {"AUTO_SOUTHWEST_CHECK_IN_USERNAME": "test_user"})
        mocker.patch.dict("os.environ", {"AUTO_SOUTHWEST_CHECK_IN_PASSWORD": "test_pass"})
        test_config = GlobalConfig()
        config_content = test_config._read_env_vars({})

        assert config_content == {"accounts": [{"username": "test_user", "password": "test_pass"}]}

    def test_read_env_vars_additional_account_successful(self, mocker: MockerFixture) -> None:
        mocker.patch.dict("os.environ", {"AUTO_SOUTHWEST_CHECK_IN_USERNAME": "test_user2"})
        mocker.patch.dict("os.environ", {"AUTO_SOUTHWEST_CHECK_IN_PASSWORD": "test_pass2"})
        test_config = GlobalConfig()
        base_config = {"accounts": [{"username": "test_user1", "password": "test_pass1"}]}
        config_content = test_config._read_env_vars(base_config)

        assert config_content == {
            "accounts": [
                {"username": "test_user1", "password": "test_pass1"},
                {"username": "test_user2", "password": "test_pass2"},
            ]
        }

    def test_read_env_vars_missing_credentials(self, mocker: MockerFixture) -> None:
        mocker.patch.dict("os.environ", {"AUTO_SOUTHWEST_CHECK_IN_USERNAME": "test_user"})
        test_config = GlobalConfig()
        config_content = test_config._read_env_vars({})

        assert config_content == {}

    def test_read_env_vars_reservation_successful(self, mocker: MockerFixture) -> None:
        mocker.patch.dict("os.environ", {"AUTO_SOUTHWEST_CHECK_IN_CONFIRMATION_NUMBER": "test_num"})
        mocker.patch.dict("os.environ", {"AUTO_SOUTHWEST_CHECK_IN_FIRST_NAME": "test_first"})
        mocker.patch.dict("os.environ", {"AUTO_SOUTHWEST_CHECK_IN_LAST_NAME": "test_last"})
        test_config = GlobalConfig()
        config_content = test_config._read_env_vars({})

        assert config_content == {
            "reservations": [
                {
                    "confirmationNumber": "test_num",
                    "firstName": "test_first",
                    "lastName": "test_last",
                }
            ]
        }

    def test_read_env_vars_additional_reservation_successful(self, mocker: MockerFixture) -> None:
        mocker.patch.dict(
            "os.environ", {"AUTO_SOUTHWEST_CHECK_IN_CONFIRMATION_NUMBER": "test_num2"}
        )
        mocker.patch.dict("os.environ", {"AUTO_SOUTHWEST_CHECK_IN_FIRST_NAME": "test_first2"})
        mocker.patch.dict("os.environ", {"AUTO_SOUTHWEST_CHECK_IN_LAST_NAME": "test_last2"})
        test_config = GlobalConfig()
        base_config = {
            "reservations": [
                {
                    "confirmationNumber": "test_num1",
                    "firstName": "test_first1",
                    "lastName": "test_last1",
                }
            ]
        }
        config_content = test_config._read_env_vars(base_config)

        assert config_content == {
            "reservations": [
                {
                    "confirmationNumber": "test_num1",
                    "firstName": "test_first1",
                    "lastName": "test_last1",
                },
                {
                    "confirmationNumber": "test_num2",
                    "firstName": "test_first2",
                    "lastName": "test_last2",
                },
            ]
        }

    def test_read_env_vars_missing_reservation(self, mocker: MockerFixture) -> None:
        mocker.patch.dict("os.environ", {"AUTO_SOUTHWEST_CHECK_IN_CONFIRMATION_NUMBER": "test_num"})
        test_config = GlobalConfig()
        config_content = test_config._read_env_vars({})

        assert not config_content

    @pytest.mark.parametrize(
        "config_content",
        [
            {"browser_path": 0},
            {"accounts": "invalid"},
            {"reservations": "invalid"},
        ],
    )
    def test_parse_config_raises_exception_with_invalid_entries(self, config_content: JSON) -> None:
        test_config = GlobalConfig()

        with pytest.raises(ConfigError):
            test_config._parse_config(config_content)

    def test_parse_config_sets_the_correct_config_values(self, mocker: MockerFixture) -> None:
        mock_account_config = mocker.patch.object(GlobalConfig, "create_account_config")
        mock_reservation_config = mocker.patch.object(GlobalConfig, "create_reservation_config")

        test_config = GlobalConfig()
        test_config._parse_config(
            {
                "browser_path": "test/browser_path",
                "check_fares": False,
                "accounts": [],
                "reservations": [],
            }
        )

        assert test_config.browser_path == "test/browser_path"
        assert test_config.check_fares is False  # Make sure it calls super._parse_config
        mock_account_config.assert_called_once_with([])
        mock_reservation_config.assert_called_once_with([])

    def test_parse_config_does_not_set_values_when_a_config_value_is_empty(self) -> None:
        test_config = GlobalConfig()
        expected_config = GlobalConfig()

        test_config._parse_config({})

        assert test_config.browser_path == expected_config.browser_path
        assert test_config.accounts == expected_config.accounts
        assert test_config.reservations == expected_config.reservations


class TestAccountConfig:
    @pytest.mark.parametrize(
        "config_content",
        [
            {"username": "user"},
            {"password": "pass"},
            {"username": 0, "password": "pass"},
            {"username": "user", "password": 0},
        ],
    )
    def test_parse_config_raises_exception_on_invalid_entries(self, config_content: JSON) -> None:
        test_config = AccountConfig()
        with pytest.raises(ConfigError):
            test_config._parse_config(config_content)

    def test_parse_config_sets_the_correct_config_values(self) -> None:
        test_config = AccountConfig()
        test_config._parse_config({"username": "user", "password": "pass", "check_fares": False})

        assert test_config.check_fares is False  # Make sure it calls super._parse_config
        assert test_config.username == "user"
        assert test_config.password == "pass"


class TestReservationConfig:
    @pytest.mark.parametrize(
        "config_content",
        [
            {"firstName": "first", "lastName": "last"},
            {"confirmationNumber": "num", "lastName": "last"},
            {"confirmationNumber": "num", "firstName": "first"},
            {"confirmationNumber": 0, "firstName": "first", "lastName": "last"},
            {"confirmationNumber": "num", "firstName": 0, "lastName": "last"},
            {"confirmationNumber": "num", "firstName": "first", "lastName": 0},
        ],
    )
    def test_parse_config_raises_exception_on_invalid_entries(self, config_content: JSON) -> None:
        test_config = ReservationConfig()
        with pytest.raises(ConfigError):
            test_config._parse_config(config_content)

    def test_parse_config_sets_the_correct_config_values(self) -> None:
        test_config = ReservationConfig()
        reservation_config = {
            "confirmationNumber": "num",
            "firstName": "first",
            "lastName": "last",
            "check_fares": False,
        }
        test_config._parse_config(reservation_config)

        assert test_config.check_fares is False  # Make sure it calls super._parse_config
        assert test_config.confirmation_number == "num"
        assert test_config.first_name == "first"
        assert test_config.last_name == "last"
