#!/usr/bin/env python3

__version__ = "v1.0"

import sys
from typing import List

from lib.flight_retriever import AccountFlightRetriever, FlightRetriever


def set_up(arguments: List[str]):
    if len(arguments) > 0 and arguments[0] in ("-v", "--version"):
        print("Auto-Southwest Check-In " + __version__)
    elif len(arguments) > 0 and arguments[0] == "--test-notifications":
        flight_retriever = FlightRetriever()

        print("Sending test notifications...")
        flight_retriever.notification_handler.send_notification("This is a test message")
    elif len(arguments) == 2:
        username = arguments[0]
        password = arguments[1]

        flight_retriever = AccountFlightRetriever(username, password)
        flight_retriever.monitor_account()
    elif len(arguments) == 3:
        confirmation_number = arguments[0]
        first_name = arguments[1]
        last_name = arguments[2]

        flight_retriever = FlightRetriever(first_name, last_name)
        flight_retriever.checkin_scheduler.refresh_headers()
        flight_retriever.schedule_reservations([{"confirmationNumber": confirmation_number}])
    else:
        print("Invalid arguments")  # TODO: Send reference on how to use the script


if __name__ == "__main__":
    arguments = sys.argv[1:]

    try:
        set_up(arguments)
    except KeyboardInterrupt:
        print("\nCtrl+C pressed. Stopping all checkins")
        sys.exit()
