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
- [Python 3.7+][0]
- [Pip][1]
- [Google Chrome][2]

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
To set up a configuration file, copy `config.example.json` to `config.json`.

### Notifications
#### Notification URLs
Users can be notified on successful and failed check-ins. This is done through the [Apprise library][3].
To start, first gather the service url you want to send notifications to (information on how to create
service urls can be found on the [Apprise Readme][4]). Then put it in your configuration file.
```json
{
  "notification_urls": "service://my_service_url"
}
```
If you have more than one service you want to send notifications to, you can put them in an array:
```json
{
  "notification_urls": [
    "service://my_first_service_url",
    "service://my_second_service_url"
  ]
}

```
#### Notification Level
You can also select the level of notifications you want to receive.
```json
{
  "notification_level": 1
}
```
Level 1 means you receive successful scheduling and check-in messages and all messages in later levels.\
Level 2 means you receive only error messages (failed scheduling and check-ins).

#### Test The Notifications
To test if the notification urls work, you can run the following command
```shell
$ python3 southwest.py --test-notifications
```


[0]: https://www.python.org/downloads/
[1]: https://pip.pypa.io/en/stable/installation/
[2]: https://www.google.com/chrome/
[3]: https://github.com/caronc/apprise
[4]: https://github.com/caronc/apprise#supported-notifications
