"""Primary script entrypoint where arguments are processed and flights are set up."""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from multiprocessing import Process
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:  # pragma: no cover
    from config import Config

__version__ = "v2.0"

__doc__ = """
Schedule a check-in:
    python3 southwest.py CONFIRMATION_NUMBER FIRST_NAME LAST_NAME

Log into your account:
    python3 southwest.py USERNAME PASSWORD

Options:
    --test-notifications Test the notification URLs configuration and exit
    -v, --verbose        Emit debug messages to stderr
    -h, --help           Display this help and exit
    -V, --version        Display version information and exit

For more information, check out https://github.com/jdholtz/auto-southwest-check-in#readme"""

LOG_FILE = "logs/auto-southwest-check-in.log"

# Use the parent logger so the logger config is applied to every module
# when using getLogger(__name__)
logger = logging.getLogger("lib")


def print_version():
    print("Auto-Southwest Check-In " + __version__)


def print_usage():
    print_version()
    print(__doc__)


def check_flags(arguments: List[str]) -> None:
    """Checks for version and help flags and exits the script on success"""
    if "--version" in arguments or "-V" in arguments:
        print_version()
        sys.exit()
    elif "--help" in arguments or "-h" in arguments:
        print_usage()
        sys.exit()


def init_logging(arguments: List[str]) -> None:
    """Sets the logger configuration for the script"""
    # Make the logging directory if it doesn't exist
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

    logger.setLevel(logging.DEBUG)  # The minimum level for every handler

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(processName)s[%(module)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=2 * 1024 * 1024, backupCount=4
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    file_handler.doRollover()  # Create a new log file when starting the application

    stream_handler = logging.StreamHandler()

    if "--verbose" in arguments or "-v" in arguments:
        stream_handler.setLevel(logging.DEBUG)
        stream_handler.setFormatter(formatter)
    else:
        stream_handler.setLevel(logging.INFO)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

    logger.debug("Initialized the application")


def set_up_accounts(config: Config) -> None:
    # pylint:disable=import-outside-toplevel
    from .flight_retriever import AccountFlightRetriever

    for account in config.accounts:
        flight_retriever = AccountFlightRetriever(config, account[0], account[1])

        # Start each account in a separate process to run them in parallel
        process = Process(target=flight_retriever.monitor_account)
        process.start()


def set_up_flights(config: Config) -> None:
    # pylint:disable=import-outside-toplevel
    from .flight_retriever import FlightRetriever

    for flight in config.flights:
        flight_retriever = FlightRetriever(config, flight[1], flight[2])

        # Start each flight in a separate process to run them in parallel
        process = Process(
            target=flight_retriever.schedule_reservations,
            args=([{"confirmationNumber": flight[0]}],),
        )
        process.start()


def set_up_check_in(arguments: List[str]):
    """Initialize a specific Flight Retriever based on the arguments passed in"""
    logger.debug("Called with %d arguments", len(arguments))

    # Imported here to avoid needing dependencies to retrieve the script's
    # version or usage
    # pylint:disable=import-outside-toplevel
    from .config import Config
    from .flight_retriever import FlightRetriever

    config = Config()

    if "--test-notifications" in arguments:
        flight_retriever = FlightRetriever(config)

        logger.info("Sending test notifications...")
        flight_retriever.notification_handler.send_notification("This is a test message")
        sys.exit()
    elif len(arguments) == 2:
        config.accounts.append([arguments[0], arguments[1]])
        logger.debug("Account added through CLI arguments")
    elif len(arguments) == 3:
        config.flights.append([arguments[0], arguments[1], arguments[2]])
        logger.debug("Flight added through CLI arguments")
    elif len(arguments) > 3:
        logger.error("Invalid arguments. For more information, try '--help'")
        sys.exit()

    logger.debug("Monitoring %d accounts and %d flights", len(config.accounts), len(config.flights))
    set_up_accounts(config)
    set_up_flights(config)


def main(arguments: List[str]) -> None:
    flags_to_remove = ["-v", "--verbose"]

    check_flags(arguments)
    init_logging(arguments)

    # Remove flags now that they are not needed (and will mess up parsing)
    arguments = [x for x in arguments if x not in flags_to_remove]
    set_up_check_in(arguments)
