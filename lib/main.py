"""Primary script entrypoint where arguments are processed and flights are set up."""

from __future__ import annotations

import multiprocessing
import os
import sys

import requests

from lib import log

from .config import IS_DOCKER, GlobalConfig, ReservationConfig
from .reservation_monitor import AccountMonitor, ReservationMonitor

IP_TIMEZONE_URL = "https://ipinfo.io/timezone"
LOG_FILE = "logs/auto-southwest-check-in.log"

logger = log.get_logger(__name__)


def get_timezone() -> str:
    """Fetches the local timezone based on the system's IP address"""
    try:
        logger.debug("Fetching local timezone")
        response = requests.get(IP_TIMEZONE_URL, timeout=5)
        response.raise_for_status()
        return response.text.strip()
    except requests.RequestException:
        logger.debug("Timezone request failed, reverting to UTC")
        return "UTC"


def test_notifications(config: GlobalConfig) -> None:
    """
    Send a test notification to all configured sources. The notification configs for every account
    and reservation are merged to ensure only one test notification is sent to each source, even
    if a URL is specified for multiple accounts or reservations.
    """
    for account in config.accounts:
        config.merge_notification_config(account)

    for reservation in config.reservations:
        config.merge_notification_config(reservation)

    new_config = ReservationConfig()
    new_config.notifications = config.notifications
    reservation_monitor = ReservationMonitor(new_config)

    logger.info("Sending test notifications to %d sources", len(new_config.notifications))
    reservation_monitor.notification_handler.send_notification("This is a test message")


def pluralize(word: str, count: int) -> str:
    """Pluralize a word to improve grammar for printed messages"""
    return word if count == 1 else word + "s"


def set_up_accounts(config: GlobalConfig, lock: multiprocessing.Lock) -> None:
    for account in config.accounts:
        account_monitor = AccountMonitor(account, lock)
        account_monitor.start()


def set_up_reservations(config: GlobalConfig, lock: multiprocessing.Lock) -> None:
    for reservation in config.reservations:
        reservation_monitor = ReservationMonitor(reservation, lock)
        reservation_monitor.start()


def set_up_check_in(arguments: list[str]) -> None:
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

    num_accounts = len(config.accounts)
    num_reservations = len(config.reservations)
    logger.info(
        "Monitoring %s %s and %s %s\n",
        num_accounts,
        pluralize("account", num_accounts),
        num_reservations,
        pluralize("reservation", num_reservations),
    )

    lock = multiprocessing.Lock()
    set_up_accounts(config, lock)
    set_up_reservations(config, lock)

    # Keep the main process alive until all processes are done so it can handle
    # keyboard interrupts
    for process in multiprocessing.active_children():
        process.join()


def main(arguments: list[str], version: str) -> None:
    log.init_main_logging()
    logger.debug("Auto-Southwest Check-In %s", version)

    if IS_DOCKER:
        # Setting timezone to avoid Southwest fingerprinting (based on browser timezone)
        timezone = get_timezone()
        os.environ["TZ"] = timezone

    # Remove flags now that they are not needed (and will mess up parsing)
    flags_to_remove = ["--debug-screenshots", "-v", "--verbose"]
    arguments = [x for x in arguments if x not in flags_to_remove]

    try:
        set_up_check_in(arguments)
    except KeyboardInterrupt:
        logger.info("\nCtrl+C pressed. Stopping all check-ins")
        sys.exit(130)
