#!/usr/bin/env python3
"""Entrypoint into the script where the arguments are passed to lib.main"""

import sys
from typing import List

__version__ = "v7.4"

__doc__ = """
Schedule a check-in:
    python3 southwest.py [options] CONFIRMATION_NUMBER FIRST_NAME LAST_NAME

Log into your account:
    python3 southwest.py [options] USERNAME PASSWORD

Options:
    --test-notifications Test the notification URLs configuration and exit
    --debug-screenshots  Take screenshots of the browser for debugging purposes. Screenshots
                         will be stored in the 'logs/' directory
    -v, --verbose        Display debug messages
    -h, --help           Display this help and exit
    -V, --version        Display version information and exit

For more information, check out https://github.com/jdholtz/auto-southwest-check-in#readme"""


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


def init(arguments: List[str]) -> None:
    check_flags(arguments)

    # Imported here to avoid needing dependencies to retrieve the script's
    # version or usage
    # pylint:disable=import-outside-toplevel
    from lib.main import main

    main(arguments, __version__)


if __name__ == "__main__":
    arguments = sys.argv[1:]
    init(arguments)
