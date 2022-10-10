#!/usr/bin/env python3
import sys
from typing import List

from lib.account import Account


def set_up(arguments: List[str]):
    if len(arguments) > 0 and arguments[0] == "--test-notifications":
        account = Account()

        print("Sending test notifications...")
        account.send_notification("This is a test message")
    elif len(arguments) == 2:
        username = arguments[0]
        password = arguments[1]

        account = Account(username, password)
        account.get_flights()
    elif len(arguments) == 3:
        confirmation_number = arguments[0]
        first_name = arguments[1]
        last_name = arguments[2]

        account = Account(first_name = first_name, last_name = last_name)
        account.get_checkin_info(confirmation_number)
    else:
        print("Invalid arguments") # TODO: Send reference on how to use the script


if __name__ == "__main__":
    arguments = sys.argv[1:]

    try:
        set_up(arguments)
    except KeyboardInterrupt:
        print("\nCtrl+C pressed. Stopping all checkins")
        sys.exit()
