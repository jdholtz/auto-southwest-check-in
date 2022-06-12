#!/usr/bin/env python3
import sys

from lib.account import Account

def set_up(arguments):
    if arguments[1] == "--test-notifications":
        print("Sending test notifications...")
        account = Account()
        account.send_notification("This is a test message")
    elif len(arguments) == 3:
        username = arguments[1]
        password = arguments[2]

        account = Account(username, password)
        account.get_flights()
    elif len(arguments) == 4:
        confirmation_number = arguments[1]
        first_name = arguments[2]
        last_name = arguments[3]

        account = Account(first_name=first_name, last_name=last_name)
        account.get_checkin_info(confirmation_number)
    else:
        print("Invalid arguments") # TODO: Send reference on how to use the script


if __name__ == "__main__":
    arguments = sys.argv

    try:
        set_up(arguments)
    except KeyboardInterrupt:
        print("\nCtrl+C pressed. Stopping all checkins")
        sys.exit()
