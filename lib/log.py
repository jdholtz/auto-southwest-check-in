import logging
import logging.handlers
import multiprocessing
import os
import sys
from pathlib import Path

LOG_FILE = "logs/auto-southwest-check-in.log"
LOG_LEVEL = logging.INFO


def init_main_logging() -> None:
    """
    Initialize the main logging setup for the script. This should only be
    called in the main process.
    """
    # Use the parent logger so the logger config is applied to every module
    # when using getLogger(__name__)
    logger = logging.getLogger("lib")
    init_logging(logger)

    logger.handlers[0].doRollover()  # Create a new log file when starting the application
    logger.debug("Initialized the application")


def init_logging(logger: logging.Logger) -> None:
    """Sets the configuration for the provided logger"""
    # Make the logging directory if it doesn't exist
    os.makedirs(Path(LOG_FILE).parent, exist_ok=True)

    logger.setLevel(logging.DEBUG)  # The minimum level for every handler

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(processName)s[%(module)s:%(lineno)d]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=2 * 1024 * 1024, backupCount=4
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()

    # Retrieve the arguments again to set the correct logging level
    # in child processes. In 'spawn' start methods, global variables
    # won't be copied, so getting the log level from the parent process
    # is complicated. Therefore, it is evaluated from the arguments.
    arguments = sys.argv[1:]
    if "--verbose" in arguments or "-v" in arguments:
        stream_handler.setLevel(logging.DEBUG)
        stream_handler.setFormatter(formatter)
    else:
        stream_handler.setLevel(logging.INFO)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)


def get_logger(name: str) -> logging.Logger:
    """
    Retrieve the logger for the current module. This is called in
    every module instead of logging.getLogger so the logger configuration
    can be set correctly.
    """
    logger = logging.getLogger(name)

    # When processes are started using the spawn method, their logger
    # configuration will not get copied over (unlike the fork start method).
    # Therefore, the configuration has to be reapplied for every child process.
    if (
        multiprocessing.get_start_method() == "spawn"
        and multiprocessing.current_process().name != "MainProcess"
    ):
        init_logging(logger)

    return logger
