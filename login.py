import sys

from scripts.account import Account


if __name__ == "__main__":
    arguments = sys.argv
    username = arguments[1]
    password = arguments[2]

    account = Account(username, password)
    flights = account.get_flights()
