"""Primary script entrypoint where arguments are processed and flights are set up."""

from __future__ import annotations

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
    -h, --help           Display this help and exit
    -v, --version        Display version information and exit

For more information, check out https://github.com/jdholtz/auto-southwest-check-in#readme"""


def print_version():
    print("Auto-Southwest Check-In " + __version__)


def print_usage():
    print_version()
    print(__doc__)


def check_flags(arguments: List[str]) -> None:
    """Checks for version and help flags and exits the script on success"""
    if "--version" in arguments or "-v" in arguments:
        print_version()
        sys.exit()
    elif "--help" in arguments or "-h" in arguments:
        print_usage()
        sys.exit()


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


def set_up(arguments: List[str]):
    """Initialize a specific Flight Retriever based on the arguments passed in"""

    # Imported here to avoid needing dependencies to retrieve the script's
    # version or usage
    # pylint:disable=import-outside-toplevel
    from .config import Config
    from .flight_retriever import FlightRetriever

    config = Config()

    if "--test-notifications" in arguments:
        flight_retriever = FlightRetriever(config)

        print("Sending test notifications...")
        flight_retriever.notification_handler.send_notification("This is a test message")
    elif len(arguments) == 2:
        config.accounts.append([arguments[0], arguments[1]])
    elif len(arguments) == 3:
        config.flights.append([arguments[0], arguments[1], arguments[2]])
    elif len(arguments) > 3:
        print("Invalid arguments. For more information, try '--help'")
        sys.exit()

    set_up_accounts(config)
    set_up_flights(config)


def main(arguments: List[str]) -> None:
    check_flags(arguments)
    set_up(arguments)
