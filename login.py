#!/usr/bin/env python3
import sys

from lib.account import Account


if __name__ == "__main__":
    arguments = sys.argv
    username = arguments[1]
    password = arguments[2]

    account = Account(username, password)
    account.get_flights()
