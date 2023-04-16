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


def test_config_sets_chromedriver_path_from_environment_variable(mocker: MockerFixture) -> None:
    mocker.patch("os.getenv", return_value="/test/path")

    test_config = config.Config()
    assert test_config.chromedriver_path == "/test/path"


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
        {"check_fares": "invalid"},
        {"chrome_version": "invalid"},
        {"chromedriver_path": None},
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
            "check_fares": True,
            "chrome_version": 10,
            "chromedriver_path": "/test/path",
            "notification_level": 20,
            "notification_urls": "test_url",
            "retrieval_interval": 30,
        }
    )

    assert test_config.check_fares is True
    assert test_config.chrome_version == 10
    assert test_config.chromedriver_path == "/test/path"
    assert test_config.notification_level == 20
    assert test_config.notification_urls == "test_url"
    assert test_config.retrieval_interval == 30 * 60 * 60


def test_parse_config_does_not_set_values_when_a_config_value_is_empty(
    mocker: MockerFixture,
) -> None:
    mock_parse_accounts = mocker.patch.object(config.Config, "_parse_accounts")
    mock_parse_flights = mocker.patch.object(config.Config, "_parse_flights")
    test_config = config.Config()
    expected_config = config.Config()

    test_config._parse_config({})

    assert test_config.check_fares == expected_config.check_fares
    assert test_config.chrome_version == expected_config.chrome_version
    assert test_config.chromedriver_path == expected_config.chromedriver_path
    assert test_config.notification_urls == expected_config.notification_urls
    assert test_config.notification_level == expected_config.notification_level
    assert test_config.retrieval_interval == expected_config.retrieval_interval
    mock_parse_accounts.assert_not_called()
    mock_parse_flights.assert_not_called()


def test_parse_config_sets_retrieval_interval_to_a_minimum() -> None:
    test_config = config.Config()
    test_config._parse_config({"retrieval_interval": -1})

    assert test_config.retrieval_interval == 1 * 60 * 60


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


def test_parse_accounts_parses_objects_correctly(mocker: MockerFixture) -> None:
    accounts = [["account1"], ["account2"]]
    mocker.patch.object(config.Config, "_parse_objects", return_value=accounts)

    test_config = config.Config()
    test_config._parse_accounts([])

    assert test_config.accounts == accounts


def test_parse_flights_parses_objects_correctly(mocker: MockerFixture) -> None:
    flights = [["flight1"], ["flight2"]]
    mocker.patch.object(config.Config, "_parse_objects", return_value=flights)

    test_config = config.Config()
    test_config._parse_flights([])

    assert test_config.flights == flights


@pytest.mark.parametrize("objects", [[""], [1], [True]])
def test_parse_objects_raises_exception_with_invalid_types(objects: List[Any]) -> None:
    test_config = config.Config()

    with pytest.raises(TypeError):
        test_config._parse_objects(objects, [], "")


def test_parse_objects_parses_every_object(mocker: MockerFixture) -> None:
    mock_parse_object = mocker.patch.object(config.Config, "_parse_object")
    test_config = config.Config()
    test_config._parse_objects([{}, {}], [], "")

    assert mock_parse_object.call_count == 2


@pytest.mark.parametrize("object_config", [{}, {"key": None}])
def test_parse_object_raises_excpetion_when_key_is_not_in_object(
    object_config: Dict[str, Any]
) -> None:
    test_config = config.Config()
    with pytest.raises(TypeError):
        test_config._parse_object(object_config, ["key"], "")


def test_parse_object_raises_exception_when_value_of_key_is_not_a_string() -> None:
    test_config = config.Config()
    with pytest.raises(TypeError):
        test_config._parse_object({"key": 1}, ["key"], "")


def test_parse_object_parses_an_object_correctly() -> None:
    obj = {"key1": "value1", "key2": "value2"}
    test_config = config.Config()
    obj_info = test_config._parse_object(obj, list(obj.keys()), "")

    assert obj_info == list(obj.values())
