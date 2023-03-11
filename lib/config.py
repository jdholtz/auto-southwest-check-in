import json
import os
import sys
from typing import Any, Dict, List

from .general import NotificationLevel
from .log import get_logger

# Type alias for JSON
JSON = Dict[str, Any]

CONFIG_FILE_NAME = "config.json"
logger = get_logger(__name__)


class Config:
    def __init__(self):
        # Default values are set
        self.accounts = []
        self.flights = []
        self.notification_level = NotificationLevel.INFO
        self.notification_urls = []
        self.retrieval_interval = 24

        # _CHROME_VERSION will be set in the Docker container
        self.chrome_version = os.getenv("_CHROME_VERSION")
        if isinstance(self.chrome_version, str):
            # Environment variables are strings but chrome_version needs
            # to be an integer
            self.chrome_version = int(self.chrome_version)

        # Set the configuration values if provided
        try:
            config = self._read_config()
            self._parse_config(config)
        except (TypeError, json.decoder.JSONDecodeError) as err:
            print("Error in configuration file:")
            print(err)
            sys.exit()

    def _read_config(self) -> JSON:
        project_dir = os.path.dirname(os.path.dirname(__file__))
        config_file = project_dir + "/" + CONFIG_FILE_NAME

        logger.debug("Reading the configuration file")
        try:
            with open(config_file) as file:
                config = json.load(file)
        except FileNotFoundError:
            logger.debug("No configuration file found. Using defaults")
            config = {}

        return config

    # This method ensures the configuration values are correct and the right types.
    # Defaults are already set in the constructor to ensure a value is never null.
    def _parse_config(self, config: JSON) -> None:
        if "accounts" in config:
            accounts = config["accounts"]

            if not isinstance(accounts, list):
                raise TypeError("'accounts' must be a list")

            self._parse_accounts(accounts)

        if "chrome_version" in config:
            self.chrome_version = config["chrome_version"]
            logger.debug("Setting chrome version to %s", self.chrome_version)

            if not isinstance(self.chrome_version, int):
                raise TypeError("'chrome_version' must be an integer")

        if "flights" in config:
            flights = config["flights"]

            if not isinstance(flights, list):
                raise TypeError("'flights' must be a list")

            self._parse_flights(flights)

        if "notification_level" in config:
            self.notification_level = config["notification_level"]
            logger.debug("Setting notification level to %s", self.notification_level)

            if not isinstance(self.notification_level, int):
                raise TypeError("'notification_level' must be an integer")

        if "notification_urls" in config:
            self.notification_urls = config["notification_urls"]

            if not isinstance(self.notification_urls, (list, str)):
                raise TypeError("'notification_urls' must be a list or string")

            notification_urls_len = (
                len(self.notification_urls) if isinstance(self.notification_urls, list) else 1
            )
            logger.debug("Using %d notification services", notification_urls_len)

        if "retrieval_interval" in config:
            self.retrieval_interval = config["retrieval_interval"]
            logger.debug("Setting retrieval interval to %s hours", self.retrieval_interval)

            if not isinstance(self.retrieval_interval, int):
                raise TypeError("'retrieval_interval' must be an integer")

            if self.retrieval_interval < 0:
                logger.warning(
                    "Setting 'retrieval_interval' to 1 hour as %s hours is too low",
                    self.retrieval_interval,
                )
                self.retrieval_interval = 1

    def _parse_accounts(self, account_config: List[JSON]) -> None:
        logger.debug("Adding %d accounts from configuration file", len(account_config))
        keys = ["username", "password"]
        accounts = self._parse_objects(account_config, keys, "account")
        self.accounts.extend(accounts)

    def _parse_flights(self, flight_config: List[JSON]) -> None:
        logger.debug("Adding %d flights from configuration file", len(flight_config))
        keys = ["confirmationNumber", "firstName", "lastName"]
        flights = self._parse_objects(flight_config, keys, "flight")
        self.flights.extend(flights)

    def _parse_objects(self, objs: List[JSON], keys: List[str], obj_type: str) -> List[List[str]]:
        parsed_objects = []
        for obj in objs:
            if not isinstance(obj, dict):
                raise TypeError(f"'{obj_type}s' must only contain dictionaries")

            parsed_object = self._parse_object(obj, keys, obj_type)
            parsed_objects.append(parsed_object)

        return parsed_objects

    def _parse_object(self, obj: JSON, keys: List[str], obj_type: str) -> List[str]:
        object_info = []
        for key in keys:
            value = obj.get(key)
            if value is None:
                raise TypeError(f"'{key}' must be in every {obj_type}")

            if not isinstance(value, str):
                raise TypeError(f"'{key}' must be a string")

            object_info.append(value)

        return object_info
