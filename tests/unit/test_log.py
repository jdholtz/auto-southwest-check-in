import logging
import multiprocessing
import sys
from typing import Iterator

import pytest
from pytest_mock import MockerFixture

from lib import log


@pytest.fixture(autouse=True)
def logger(mocker: MockerFixture) -> Iterator[logging.Logger]:
    logger = logging.getLogger("lib")
    # Make sure logs aren't written to a file
    mock_file_handler = mocker.patch("logging.handlers.RotatingFileHandler")
    mock_file_handler.return_value.level = logging.DEBUG

    yield logger

    logger.handlers = []  # Clean up after test


def test_init_main_logging_initializes_the_logging_correctly(logger: logging.Logger) -> None:
    log.init_main_logging()
    logger.handlers[0].doRollover.assert_called_once()


@pytest.mark.parametrize(
    ["argument", "verbosity_level"],
    [
        ("", logging.INFO),
        ("-v", logging.DEBUG),
        ("--verbose", logging.DEBUG),
    ],
)
def test_init_logging_sets_verbosity_level_correctly(
    mocker: MockerFixture, argument: str, verbosity_level: int, logger: logging.Logger
) -> None:
    mocker.patch("logging.handlers.RotatingFileHandler")
    mock_makedirs = mocker.patch("os.makedirs")

    sys.argv = ["", argument]
    log.init_logging(logger)

    mock_makedirs.assert_called_once()
    assert len(logger.handlers) == 2, "Expected a file and console handler to be created"
    assert logger.handlers[1].level == verbosity_level


def test_get_logger_does_not_initialize_logger_with_fork_start_method(
    mocker: MockerFixture,
) -> None:
    mocker.patch("multiprocessing.get_start_method", return_value="fork")
    mock_init_logging = mocker.patch("lib.log.init_logging")

    multiprocessing.current_process().name = "Process-1"
    log.get_logger("lib")
    mock_init_logging.assert_not_called()


def test_get_logger_does_not_initialize_logger_in_main_process(mocker: MockerFixture) -> None:
    mock_init_logging = mocker.patch("lib.log.init_logging")

    multiprocessing.current_process().name = "MainProcess"
    log.get_logger("lib")
    mock_init_logging.assert_not_called()


def test_get_logger_initializes_logger_with_spawn_start_method(mocker: MockerFixture) -> None:
    mocker.patch("multiprocessing.get_start_method", return_value="spawn")
    mock_init_logging = mocker.patch("lib.log.init_logging")

    multiprocessing.current_process().name = "Process-1"
    log.get_logger("lib")
    mock_init_logging.assert_called_once()
