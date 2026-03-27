"""Minimal config stub for the worker.
Only provides the values needed by webdriver.py and other lib modules."""

import os

IS_DOCKER = os.environ.get("AUTO_SOUTHWEST_CHECK_IN_DOCKER") == "1"


class ConfigError(Exception):
    pass
