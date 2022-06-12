## Auto-Southwest Check-In
Running this script will automatically check you into your flight 24 hours before your flight

## Table of Contents
- [Installation](#installation)
    * [Prerequisites](#prerequisites)
- [Using The Script](#using-the-script)
- [Configuration](#configuration)
    * [Notifications](#notifications)

## Installation

### Prerequisites
- [Python 3.10][0]
- [Pip][1]
- [Google Chrome (Version 101+)][2]

First, download the script onto your computer
```shell
$ git clone https://github.com/jdholtz/auto-southwest-check-in.git
$ cd auto-southwest-check-in
```
Then, install the needed packages for the script
```shell
$ pip install -r requirements.txt
```

## Using The Script
To schedule a check-in, run the following command
```shell
$ python3 southwest.py CONFIRMATION_NUMBER FIRST_NAME LAST_NAME
```
Alternatively, you can log in to your account, which will automatically check you in to all of your flights
```shell
$ python3 southwest.py USERNAME PASSWORD
```

## Configuration
### Notifications
**This feature is currently in its beta version and can be found on the [notifications][3] branch.** \
If you use this, please let me know if it worked or not in the [Issue #4][4] thread.


[0]: https://www.python.org/downloads/
[1]: https://pip.pypa.io/en/stable/installation/
[2]: https://www.google.com/chrome/
[3]: https://github.com/jdholtz/auto-southwest-check-in/tree/notifications
[4]: https://github.com/jdholtz/auto-southwest-check-in/issues/4
