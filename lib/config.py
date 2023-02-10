import json
import os
import sys
from typing import Any, Dict, List

from .general import NotificationLevel

# Type alias for JSON
JSON = Dict[str, Any]

CONFIG_FILE_NAME = "config.json"


class Config:
    def __init__(self):
        # Default values are set
        self.accounts = []
        self.chrome_version = 109
        self.flights = []
        self.notification_level = NotificationLevel.INFO
        self.notification_urls = []
        self.retrieval_interval = 24

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

        try:
            with open(config_file) as file:
                config = json.load(file)
        except FileNotFoundError:
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

            if not isinstance(self.chrome_version, int):
                raise TypeError("'chrome_version' must be an integer")

        if "flights" in config:
            flights = config["flights"]

            if not isinstance(flights, list):
                raise TypeError("'flights' must be a list")

            self._parse_flights(flights)

        if "notification_level" in config:
            self.notification_level = config["notification_level"]

            if not isinstance(self.notification_level, int):
                raise TypeError("'notification_level' must be an integer")

        if "notification_urls" in config:
            self.notification_urls = config["notification_urls"]

            if not isinstance(self.notification_urls, (list, str)):
                raise TypeError("'notification_urls' must be a list or string")

        if "retrieval_interval" in config:
            self.retrieval_interval = config["retrieval_interval"]

            if not isinstance(self.retrieval_interval, int):
                raise TypeError("'retrieval_interval' must be an integer")

            if self.retrieval_interval < 1:
                print(
                    f"Setting 'retrieval_interval' to one as {self.retrieval_interval} hours is too low"
                )
                self.retrieval_interval = 1

    def _parse_accounts(self, accounts: List[JSON]) -> None:
        for account in accounts:
            if not isinstance(account, dict):
                raise TypeError("'accounts' must only contain dictionaries")

            self._parse_account(account)

    def _parse_account(self, account: JSON) -> None:
        if "username" not in account:
            raise TypeError("'username' must be in every account")

        if "password" not in account:
            raise TypeError("'password' must be in every account")

        username = account["username"]
        if not isinstance(username, str):
            raise TypeError("'username' must be a string")

        password = account["password"]
        if not isinstance(password, str):
            raise TypeError("'password' must be a string")

        self.accounts.append([username, password])

    def _parse_flights(self, flights: List[JSON]) -> None:
        for flight in flights:
            if not isinstance(flight, dict):
                raise TypeError("'flights' must only contain dictionaries")

            self._parse_flight(flight)

    def _parse_flight(self, flight: JSON) -> None:
        if "confirmationNumber" not in flight:
            raise TypeError("'confirmationNumber' must be in every flight")

        if "firstName" not in flight:
            raise TypeError("'firstName' must be in every flight")

        if "lastName" not in flight:
            raise TypeError("'lastName' must be in every flight")

        confirmation_number = flight["confirmationNumber"]
        if not isinstance(confirmation_number, str):
            raise TypeError("'confirmationNumber' must be a string")

        first_name = flight["firstName"]
        if not isinstance(first_name, str):
            raise TypeError("'firstName' must be a string")

        last_name = flight["lastName"]
        if not isinstance(last_name, str):
            raise TypeError("'lastName' must be a string")

        self.flights.append([confirmation_number, first_name, last_name])
