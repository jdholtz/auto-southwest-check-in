"""Primary script entrypoint where arguments are processed and flights are set up."""

from __future__ import annotations

import sys
from multiprocessing import Process
from typing import TYPE_CHECKING, List

from lib import log

if TYPE_CHECKING:
    from lib.config import Config

__version__ = "v4.2"

__doc__ = """
Schedule a check-in:
    python3 southwest.py [options] CONFIRMATION_NUMBER FIRST_NAME LAST_NAME

Log into your account:
    python3 southwest.py [options] USERNAME PASSWORD

Options:
    --test-notifications Test the notification URLs configuration and exit
    -v, --verbose        Display debug messages
    -h, --help           Display this help and exit
    -V, --version        Display version information and exit

For more information, check out https://github.com/jdholtz/auto-southwest-check-in#readme"""

LOG_FILE = "logs/auto-southwest-check-in.log"

logger = log.get_logger(__name__)


def print_version() -> None:
    print("Auto-Southwest Check-In " + __version__)


def print_usage() -> None:
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


def set_up_accounts(config: Config) -> None:
    # pylint:disable=import-outside-toplevel
    from .reservation_monitor import AccountMonitor

    for account in config.accounts:
        account_monitor = AccountMonitor(config, account[0], account[1])

        # Start each account monitor in a separate process to run them in parallel
        process = Process(target=account_monitor.monitor)
        process.start()


def set_up_reservations(config: Config) -> None:
    # pylint:disable=import-outside-toplevel
    from .reservation_monitor import ReservationMonitor

    for reservation in config.reservations:
        reservation_monitor = ReservationMonitor(config, reservation[1], reservation[2])

        # Start each reservation monitor in a separate process to run them in parallel
        process = Process(
            target=reservation_monitor.monitor,
            args=([{"confirmationNumber": reservation[0]}],),
        )
        process.start()


def set_up_check_in(arguments: List[str]) -> None:
    """
    Initialize reservation and account monitoring based on the configuration
    and arguments passed in
    """
    logger.debug("Called with %d arguments", len(arguments))

    # Imported here to avoid needing dependencies to retrieve the script's
    # version or usage
    # pylint:disable=import-outside-toplevel
    from .config import Config
    from .reservation_monitor import ReservationMonitor

    config = Config()

    if "--test-notifications" in arguments:
        reservation_monitor = ReservationMonitor(config)

        logger.info("Sending test notifications...")
        reservation_monitor.notification_handler.send_notification("This is a test message")
        sys.exit()
    elif len(arguments) == 2:
        config.accounts.append([arguments[0], arguments[1]])
        logger.debug("Account added through CLI arguments")
    elif len(arguments) == 3:
        config.reservations.append([arguments[0], arguments[1], arguments[2]])
        logger.debug("Reservation added through CLI arguments")
    elif len(arguments) > 3:
        logger.error("Invalid arguments. For more information, try '--help'")
        sys.exit(2)

    logger.debug(
        "Monitoring %d accounts and %d reservations", len(config.accounts), len(config.reservations)
    )
    set_up_accounts(config)
    set_up_reservations(config)


def main(arguments: List[str]) -> None:
    flags_to_remove = ["-v", "--verbose"]

    check_flags(arguments)
    log.init_main_logging()

    # Remove flags now that they are not needed (and will mess up parsing)
    arguments = [x for x in arguments if x not in flags_to_remove]
    set_up_check_in(arguments)
