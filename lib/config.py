import json
import sys
from pathlib import Path
from typing import Any, Dict, List

from .log import get_logger
from .utils import NotificationLevel

# Type alias for JSON
JSON = Dict[str, Any]

CONFIG_FILE_NAME = "config.json"
logger = get_logger(__name__)


# A custom exception for type or value errors in the configuration file
class ConfigError(Exception):
    pass


class Config:
    def __init__(self) -> None:
        # Default values are set
        self.browser_path = None
        self.check_fares = True
        self.notification_level = NotificationLevel.INFO
        self.notification_urls = []
        self.retrieval_interval = 24 * 60 * 60

    def create(self, config_json: JSON, global_config: "GlobalConfig") -> None:
        self._merge_globals(global_config)
        self._parse_config(config_json)

    def _merge_globals(self, global_config: "GlobalConfig") -> None:
        """
        Each account and reservation config inherits the global
        configuration first. If specific options are set for an account
        or reservation, those will override the global configuration.
        """
        self.check_fares = global_config.check_fares
        self.browser_path = global_config.browser_path
        self.notification_level = global_config.notification_level
        self.notification_urls.extend(global_config.notification_urls)
        self.retrieval_interval = global_config.retrieval_interval

    def _parse_config(self, config: JSON) -> None:
        """
        Ensures every configuration option is valid. Raises a ConfigError when
        invalid values are found.
        """
        if "check_fares" in config:
            self.check_fares = config["check_fares"]
            logger.debug("Setting check fares to %s", self.check_fares)

            if not isinstance(self.check_fares, bool):
                raise ConfigError("'check_fares' must be a boolean")

        if "notification_level" in config:
            notification_level = config["notification_level"]
            try:
                self.notification_level = NotificationLevel(notification_level)
            except ValueError as err:
                raise ConfigError(
                    f"'{notification_level}' is not a valid notification level"
                ) from err

            logger.debug("Setting notification level to %s", repr(self.notification_level))

        if "notification_urls" in config:
            notification_urls = config["notification_urls"]

            if not isinstance(notification_urls, (list, str)):
                raise ConfigError("'notification_urls' must be a list or string")

            # Make sure that empty strings don't get added to the list
            if isinstance(notification_urls, str) and len(notification_urls) > 0:
                notification_urls = [notification_urls]

            self.notification_urls.extend(notification_urls)
            logger.debug("Using %d notification services", len(self.notification_urls))

        if "retrieval_interval" in config:
            self.retrieval_interval = config["retrieval_interval"]
            logger.debug("Setting retrieval interval to %s hours", self.retrieval_interval)

            if not isinstance(self.retrieval_interval, int):
                raise ConfigError("'retrieval_interval' must be an integer")

            if self.retrieval_interval < 0:
                logger.warning(
                    "Setting 'retrieval_interval' to 0 hours as %s hours is too low",
                    self.retrieval_interval,
                )
                self.retrieval_interval = 0

            # Convert hours to seconds
            self.retrieval_interval *= 3600


class GlobalConfig(Config):
    def __init__(self) -> None:
        super().__init__()
        self.accounts = []
        self.reservations = []

    def initialize(self) -> JSON:
        logger.debug("Initializing configuration file")

        try:
            config = self._read_config()
            self._parse_config(config)
        except (ConfigError, json.decoder.JSONDecodeError) as err:
            print("Error in configuration file:")
            print(err)
            sys.exit(1)

    def create_account_config(self, accounts: List[JSON]) -> None:
        logger.debug("Creating configurations for %d accounts", len(accounts))
        for account_json in accounts:
            account_config = AccountConfig()
            account_config.create(account_json, self)
            self.accounts.append(account_config)

    def create_reservation_config(self, reservations: List[JSON]) -> None:
        logger.debug("Creating configurations for %d reservations", len(reservations))
        for reservation_json in reservations:
            reservation_config = ReservationConfig()
            reservation_config.create(reservation_json, self)
            self.reservations.append(reservation_config)

    def _read_config(self) -> JSON:
        project_dir = Path(__file__).parents[1]
        config_file = project_dir / CONFIG_FILE_NAME

        logger.debug("Reading the configuration file")
        try:
            config = json.loads(config_file.read_text())
        except FileNotFoundError:
            logger.debug("No configuration file found. Using defaults")
            config = {}

        if not isinstance(config, dict):
            raise ConfigError("Configuration must be a JSON dictionary")

        return config

    def _parse_config(self, config: JSON) -> None:
        super()._parse_config(config)

        if "browser_path" in config:
            self.browser_path = config["browser_path"]
            logger.debug("Setting custom Browser path")

            if not isinstance(self.browser_path, str):
                raise ConfigError("'browser_path' must be a string")

        if "accounts" in config:
            accounts = config["accounts"]

            if not isinstance(accounts, list):
                raise ConfigError("'accounts' must be a list")

            self.create_account_config(accounts)

        if "reservations" in config:
            reservations = config["reservations"]

            if not isinstance(reservations, list):
                raise ConfigError("'reservations' must be a list")

            self.create_reservation_config(reservations)


class AccountConfig(Config):
    def __init__(self) -> None:
        super().__init__()
        self.username = None
        self.password = None
        self.first_name = None
        self.last_name = None

    def _parse_config(self, config: JSON) -> None:
        super()._parse_config(config)

        keys = ["username", "password"]
        for key in keys:
            if key not in config:
                raise ConfigError(f"'{key}' must be in every account")

            if not isinstance(config[key], str):
                raise ConfigError(f"'{key}' in account must be a string")

        self.username = config["username"]
        self.password = config["password"]


class ReservationConfig(Config):
    def __init__(self) -> None:
        super().__init__()
        self.confirmation_number = None
        self.first_name = None
        self.last_name = None

    def _parse_config(self, config: JSON) -> None:
        super()._parse_config(config)

        keys = ["confirmationNumber", "firstName", "lastName"]
        for key in keys:
            if key not in config:
                raise ConfigError(f"'{key}' must be in every reservation")

            if not isinstance(config[key], str):
                raise ConfigError(f"'{key}' in reservation must be a string")

        self.confirmation_number = config["confirmationNumber"]
        self.first_name = config["firstName"]
        self.last_name = config["lastName"]
