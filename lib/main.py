"""Primary script entrypoint where arguments are processed and flights are set up."""

from __future__ import annotations

import multiprocessing
import sys
from typing import List

from lib import log

from .config import GlobalConfig, ReservationConfig
from .reservation_monitor import AccountMonitor, ReservationMonitor

LOG_FILE = "logs/auto-southwest-check-in.log"

logger = log.get_logger(__name__)


def get_notification_urls(config: GlobalConfig) -> List[str]:
    """
    Get all notification URLS in the global config, each account, and each
    reservation. Removes duplicates so notifications are not sent twice to
    the same source.
    """
    notification_urls = config.notification_urls

    for account in config.accounts:
        notification_urls.extend(account.notification_urls)

    for reservation in config.reservations:
        notification_urls.extend(reservation.notification_urls)

    # Remove duplicates
    notification_urls = list(set(notification_urls))
    return notification_urls


def test_notifications(config: GlobalConfig) -> None:
    notification_urls = get_notification_urls(config)

    new_config = ReservationConfig()
    new_config.notification_urls = notification_urls
    reservation_monitor = ReservationMonitor(new_config)

    logger.info("Sending test notifications to %d sources", len(notification_urls))
    reservation_monitor.notification_handler.send_notification("This is a test message")


def set_up_accounts(config: GlobalConfig, lock: multiprocessing.Lock) -> None:
    for account in config.accounts:
        account_monitor = AccountMonitor(account, lock)
        account_monitor.start()


def set_up_reservations(config: GlobalConfig, lock: multiprocessing.Lock) -> None:
    for reservation in config.reservations:
        reservation_monitor = ReservationMonitor(reservation, lock)
        reservation_monitor.start()


def set_up_check_in(arguments: List[str]) -> None:
    """
    Initialize reservation and account monitoring based on the configuration
    and arguments passed in
    """
    logger.debug("Called with %d arguments", len(arguments))

    config = GlobalConfig()
    config.initialize()

    if "--test-notifications" in arguments:
        test_notifications(config)
        sys.exit()
    elif len(arguments) == 2:
        logger.debug("Adding account through CLI arguments")
        account = {"username": arguments[0], "password": arguments[1]}
        config.create_account_config([account])
    elif len(arguments) == 3:
        logger.debug("Adding reservation through CLI arguments")
        reservation = {
            "confirmationNumber": arguments[0],
            "firstName": arguments[1],
            "lastName": arguments[2],
        }
        config.create_reservation_config([reservation])
    elif len(arguments) > 3:
        logger.error("Invalid arguments. For more information, try '--help'")
        sys.exit(2)

    logger.debug(
        "Monitoring %d accounts and %d reservations", len(config.accounts), len(config.reservations)
    )
    lock = multiprocessing.Lock()
    set_up_accounts(config, lock)
    set_up_reservations(config, lock)

    # Keep the main process alive until all processes are done so it can handle
    # keyboard interrupts
    for process in multiprocessing.active_children():
        process.join()


def main(arguments: List[str], version: str) -> None:
    log.init_main_logging()
    logger.debug("Auto-Southwest Check-In %s", version)

    # Remove flags now that they are not needed (and will mess up parsing)
    flags_to_remove = ["--debug-screenshots", "-v", "--verbose"]
    arguments = [x for x in arguments if x not in flags_to_remove]

    try:
        set_up_check_in(arguments)
    except KeyboardInterrupt:
        logger.info("\nCtrl+C pressed. Stopping all check-ins")
        sys.exit(130)
