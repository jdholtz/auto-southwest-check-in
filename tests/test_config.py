import os
from typing import Any, Dict, List

import pytest
from pytest_mock import MockerFixture

from lib import config

# This needs to be accessed to be tested
# pylint: disable=protected-access


# Make sure we don't actually read the config file. The
# mocks can still be overriden in each test
@pytest.fixture(autouse=True)
def mock_open(mocker: MockerFixture) -> None:
    mocker.patch("builtins.open")
    mocker.patch("json.load")


def test_config_sets_chrome_version_from_the_environment_variable(mocker: MockerFixture) -> None:
    mocker.patch("os.getenv", return_value="10")

    test_config = config.Config()
    assert test_config.chrome_version == 10


def test_config_exits_on_error_in_config_file(mocker: MockerFixture) -> None:
    mocker.patch.object(config.Config, "_parse_config", side_effect=TypeError())

    with pytest.raises(SystemExit):
        config.Config()


def test_read_config_reads_the_config_file_correctly(mocker: MockerFixture) -> None:
    mock_open = mocker.patch("builtins.open")
    mocker.patch("json.load", return_value={"test": "data"})

    test_config = config.Config()
    config_content = test_config._read_config()

    assert config_content == {"test": "data"}
    mock_open.assert_called_with(
        os.path.dirname(os.path.dirname(__file__)) + "/" + config.CONFIG_FILE_NAME
    )


def test_read_config_returns_empty_config_when_file_is_not_found(mocker: MockerFixture) -> None:
    mocker.patch("builtins.open", side_effect=FileNotFoundError())

    test_config = config.Config()
    config_content = test_config._read_config()

    assert config_content == {}


@pytest.mark.parametrize(
    "config_content",
    [
        {"accounts": "invalid"},
        {"chrome_version": "invalid"},
        {"flights": "invalid"},
        {"notification_level": "invalid"},
        {"notification_urls": None},
        {"retrieval_interval": "invalid"},
    ],
)
def test_parse_config_raises_exception_with_invalid_entries(config_content: Dict[str, Any]) -> None:
    test_config = config.Config()

    with pytest.raises(TypeError):
        test_config._parse_config(config_content)


def test_parse_config_sets_the_correct_config_values() -> None:
    test_config = config.Config()
    test_config._parse_config(
        {
            "chrome_version": 10,
            "notification_level": 20,
            "notification_urls": "test_url",
            "retrieval_interval": 30,
        }
    )

    assert test_config.chrome_version == 10
    assert test_config.notification_level == 20
    assert test_config.notification_urls == "test_url"
    assert test_config.retrieval_interval == 30


def test_parse_config_does_not_set_values_when_a_config_value_is_empty(
    mocker: MockerFixture,
) -> None:
    mock_parse_accounts = mocker.patch.object(config.Config, "_parse_accounts")
    mock_parse_flights = mocker.patch.object(config.Config, "_parse_flights")
    test_config = config.Config()
    expected_config = config.Config()

    test_config._parse_config({})

    assert test_config.notification_urls == expected_config.notification_urls
    assert test_config.notification_level == expected_config.notification_level
    assert test_config.retrieval_interval == test_config.retrieval_interval
    mock_parse_accounts.assert_not_called()
    mock_parse_flights.assert_not_called()


def test_parse_config_sets_retrieval_interval_to_a_minimum() -> None:
    test_config = config.Config()
    test_config._parse_config({"retrieval_interval": -1})

    assert test_config.retrieval_interval == 1


def test_parse_config_parses_accounts(mocker: MockerFixture) -> None:
    mock_parse_accounts = mocker.patch.object(config.Config, "_parse_accounts")
    test_config = config.Config()
    test_config._parse_config({"accounts": []})

    mock_parse_accounts.assert_called_once()


def test_parse_config_parses_flights(mocker: MockerFixture) -> None:
    mock_parse_flights = mocker.patch.object(config.Config, "_parse_flights")
    test_config = config.Config()
    test_config._parse_config({"flights": []})

    mock_parse_flights.assert_called_once()


@pytest.mark.parametrize("account_content", [[""], [1], [True]])
def test_parse_accounts_raises_exception_with_invalid_entries(account_content: List[Any]) -> None:
    test_config = config.Config()

    with pytest.raises(TypeError):
        test_config._parse_accounts(account_content)


def test_parse_accounts_parses_every_account(mocker: MockerFixture) -> None:
    mock_parse_account = mocker.patch.object(config.Config, "_parse_account")
    test_config = config.Config()
    test_config._parse_accounts([{}, {}])

    assert mock_parse_account.call_count == 2


@pytest.mark.parametrize(
    "account_content",
    [
        {},
        {"username": ""},  # No password
        {"password": ""},  # No username
        {"username": 1, "password": ""},  # Invalid username
        {"username": "", "password": 1},  # Invalid password
    ],
)
def test_parse_account_raises_exception_with_invalid_entries(account_content: List[Any]) -> None:
    test_config = config.Config()

    with pytest.raises(TypeError):
        test_config._parse_account(account_content)


def test_parse_account_adds_an_account() -> None:
    test_config = config.Config()
    test_config._parse_account({"username": "user", "password": "pass"})

    assert len(test_config.accounts) == 1
    assert test_config.accounts[0] == ["user", "pass"]


@pytest.mark.parametrize("flight_content", [[""], [1], [True]])
def test_parse_flights_raises_exception_with_invalid_entries(flight_content: List[Any]) -> None:
    test_config = config.Config()

    with pytest.raises(TypeError):
        test_config._parse_flights(flight_content)


def test_parse_flights_parses_every_flight(mocker: MockerFixture) -> None:
    mock_parse_flight = mocker.patch.object(config.Config, "_parse_flight")
    test_config = config.Config()
    test_config._parse_flights([{}, {}])

    assert mock_parse_flight.call_count == 2


@pytest.mark.parametrize(
    "flight_content",
    [
        {},
        {"firstName": "", "lastName": ""},  # No confirmation number
        {"confirmationNumber": "", "lastName": ""},  # No first name
        {"confirmationNumber": "", "firstName": ""},  # No first name
        {"confirmationNumber": 1, "firstName": "", "lastName": ""},  # Invalid confirmation number
        {"confirmationNumber": "", "firstName": 1, "lastName": ""},  # Invalid first name
        {"confirmationNumber": "", "firstName": "", "lastName": 1},  # Invalid last name
    ],
)
def test_parse_flight_raises_exception_with_invalid_entries(flight_content: List[Any]) -> None:
    test_config = config.Config()

    with pytest.raises(TypeError):
        test_config._parse_flight(flight_content)


def test_parse_flight_adds_a_flight() -> None:
    test_config = config.Config()
    test_config._parse_flight({"confirmationNumber": "num", "firstName": "John", "lastName": "Doe"})

    assert len(test_config.flights) == 1
    assert test_config.flights[0] == ["num", "John", "Doe"]
