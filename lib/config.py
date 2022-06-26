import json
import sys
from typing import Any, Dict

CONFIG_FILE_NAME = "config.json"


class Config():
    def __init__(self):
        # First, read the config file
        config = self._get_config()

        # Then, set the configuration values if provided. Otherwise, set defaults
        try:
            self._parse_config(config)
        except TypeError as err:
            print("Error in configuration file:")
            print(err)
            sys.exit()

    def _get_config(self) -> Dict[str, Any]:
        parent_dir = sys.path[0]
        config_file = str(parent_dir) + "/" + CONFIG_FILE_NAME

        config = {}
        try:
            with open(config_file) as file:
                config = json.load(file)
        except FileNotFoundError:
            pass

        return config

    # This method ensures the configuration values are correct and the right types.
    # A default value is set if no value is provided in the configuration file.
    def _parse_config(self, config: Dict[str, Any]) -> None:
        # Default values are set here
        self.notification_urls = []

        if "notification_urls" in config:
            self.notification_urls = config["notification_urls"]

            if not isinstance(self.notification_urls, list | str):
                raise TypeError("'notification_urls' must be a list or string")
