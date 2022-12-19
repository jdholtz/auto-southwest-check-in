"""Primary script entrypoint where arguments are processed and flights are set up."""

__version__ = "v1.0"

import sys
from typing import List

USAGE = """
Schedule a check-in:
    python3 southwest.py CONFIRMATION_NUMBER FIRST_NAME LAST_NAME

Log into your account:
    python3 southwest.py USERNAME PASSWORD

Options:
    --test-notifications Test the notification URLs configuration and exit
    -h, --help           Display this help and exit
    -v, --version        Display version information and exit

For more information, check out the README"""


def print_version():
    print("Auto-Southwest Check-In " + __version__)


def print_usage():
    print_version()
    print(USAGE)


def check_flags(arguments: List[str]) -> None:
    """Checks for version and help flags and exits the script on success"""
    if "--version" in arguments or "-v" in arguments:
        print_version()
        sys.exit()
    elif len(arguments) == 0 or "--help" in arguments or "-h" in arguments:
        print_usage()
        sys.exit()


def set_up(arguments: List[str]):
    """Initialize a specific Flight Retriever based on the arguments passed in"""

    # Imported here to avoid needing dependencies downloaded to retrieve the script's
    # version or usage
    # pylint:disable=import-outside-toplevel
    from .flight_retriever import AccountFlightRetriever, FlightRetriever

    if "--test-notifications" in arguments:
        flight_retriever = FlightRetriever()

        print("Sending test notifications...")
        flight_retriever.notification_handler.send_notification("This is a test message")
    elif len(arguments) == 2:
        username = arguments[0]
        password = arguments[1]

        flight_retriever = AccountFlightRetriever(username, password)
        flight_retriever.monitor_account()
    elif len(arguments) == 3:
        confirmation_number = arguments[0]
        first_name = arguments[1]
        last_name = arguments[2]

        flight_retriever = FlightRetriever(first_name, last_name)
        flight_retriever.checkin_scheduler.refresh_headers()
        flight_retriever.schedule_reservations([{"confirmationNumber": confirmation_number}])
    else:
        print("Invalid arguments. For more information, try '--help'")


def main(arguments: List[str]) -> None:
    check_flags(arguments)
    set_up(arguments)
