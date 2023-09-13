"""Tests various functionalities with the arguments that can be passed into the script"""

import json
import logging
from typing import Iterator

import pytest
from pytest_mock import MockerFixture

from lib import main


@pytest.fixture(autouse=True)
def logger(mocker: MockerFixture) -> Iterator[logging.Logger]:
    logger = logging.getLogger("lib")
    # Make sure logs aren't written to a file
    mock_file_handler = mocker.patch("logging.handlers.RotatingFileHandler")
    mock_file_handler.return_value.level = logging.DEBUG

    yield logger

    logger.handlers = []  # Clean up after each test


@pytest.fixture(autouse=True)
def mock_read_config(mocker: MockerFixture) -> None:
    # Don't ever read the actually config file. Will be mocked within the test
    # if a certain config needs to be used
    mocker.patch("pathlib.Path.read_text", side_effect=FileNotFoundError)


@pytest.mark.parametrize("flag", ["-V", "--version"])
def test_version_is_printed(flag: str, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main.main([flag])

    assert main.__version__ in capsys.readouterr().out


@pytest.mark.parametrize("flag", ["-h", "--help"])
def test_help_is_printed(flag: str, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main.main([flag])

    output = capsys.readouterr().out
    assert main.__version__ in output
    assert main.__doc__ in output


def test_notifications_are_tested(mocker: MockerFixture) -> None:
    config = {
        "notification_urls": ["test_global_1", "test_global_2"],
        "accounts": [
            {
                "username": "test_user",
                "password": "test_pass",
                "notification_urls": "test_account_1",
            },
        ],
        "reservations": [
            {
                "confirmationNumber": "TEST",
                "firstName": "Mererid",
                "lastName": "Marian",
                "notification_urls": ["test_global_1", "test_reservation_1"],
            },
        ],
    }

    mocker.patch("pathlib.Path.read_text", return_value=json.dumps(config))

    mock_apprise = mocker.patch("apprise.Apprise")

    with pytest.raises(SystemExit):
        main.main(["--test-notifications"])

    mock_apprise.assert_called_once()

    expected_urls = ["test_global_1", "test_global_2", "test_account_1", "test_reservation_1"]
    called_urls = mock_apprise.call_args.args[0]

    assert len(called_urls) == 4
    assert all(url in called_urls for url in expected_urls)
    mock_apprise.return_value.notify.assert_called_once()


@pytest.mark.parametrize("verbose_flag", ["-v", "--verbose"])
def test_account_from_command_line_with_verbose(
    mocker: MockerFixture, verbose_flag: str, logger: logging.Logger
) -> None:
    mock_process = mocker.patch("multiprocessing.Process").return_value
    mocker.patch("multiprocessing.active_children", return_value=[mock_process])

    args = ["test_user", "test_pass", verbose_flag]
    # sys.argv is used instead of the args passed in to the log module (it also would have
    # southwest.py prepended to it in real use)
    mocker.patch("sys.argv", ["test_file"] + args)

    main.main(args)

    mock_process.start.assert_called_once()
    mock_process.join.assert_called_once()

    assert logger.handlers[1].level == logging.DEBUG


def test_reservation_from_command_line_without_verbose(
    mocker: MockerFixture, logger: logging.Logger
) -> None:
    mock_process = mocker.patch("multiprocessing.Process").return_value
    mocker.patch("multiprocessing.active_children", return_value=[mock_process])

    args = ["TEST", "Charli", "Silvester"]
    # sys.argv is used instead of the args passed in to the log module (it also would have
    # southwest.py prepended to it in real use)
    mocker.patch("sys.argv", ["test_file"] + args)

    main.main(args)

    mock_process.start.assert_called_once()
    mock_process.join.assert_called_once()

    assert logger.handlers[1].level == logging.INFO


def test_accounts_and_reservations_from_config(mocker: MockerFixture) -> None:
    config = {
        "accounts": [{"username": "test_user", "password": "test_pass"}],
        "reservations": [
            {"confirmationNumber": "TEST", "firstName": "Nana", "lastName": "Linus"},
        ],
    }
    mocker.patch("pathlib.Path.read_text", return_value=json.dumps(config))

    mock_process = mocker.patch("multiprocessing.Process").return_value
    mocker.patch("multiprocessing.active_children", return_value=[mock_process, mock_process])

    main.main([])

    assert mock_process.start.call_count == 2
    assert mock_process.join.call_count == 2


def test_error_on_invalid_arguments() -> None:
    with pytest.raises(SystemExit):
        main.main(["most", "definitely", "invalid", "arguments"])
