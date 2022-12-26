## Auto-Southwest Check-In
Running this script will automatically check you into your flight 24 hours before your flight.

This script can also log in to your Southwest account and automatically schedule check-ins as
flights are scheduled.

**Note**: If you are checking into an international flight, make sure to fill out all the passport
information beforehand.

## Table of Contents
- [Installation](#installation)
    * [Prerequisites](#prerequisites)
    * [Upgrading](#upgrading)
- [Using The Script](#using-the-script)
    * [Running In Docker](#running-in-docker)
- [Configuration](#configuration)
    * [Notifications](#notifications)
    * [Retrieval Interval](#retrieval-interval)

## Installation

### Prerequisites
- [Python 3.7+][0]
- [Pip][1]
- [Google Chrome (Version 101+)][2]

First, download the script onto your computer
```shell
git clone https://github.com/jdholtz/auto-southwest-check-in.git
cd auto-southwest-check-in
```
Then, install the needed packages for the script
```shell
pip install -r requirements.txt
```

### Upgrading
When updating the script, it is important to follow the [Changelog](CHANGELOG.md) for any actions
that need to be performed.

To get the script's current version, run the following command:
```shell
python3 southwest.py --version
```

To update the script, simply run:
```shell
git pull
```

## Using The Script
To schedule a check-in, run the following command:
```shell
python3 southwest.py CONFIRMATION_NUMBER FIRST_NAME LAST_NAME
```
Alternatively, you can log in to your account, which will automatically check you in to all of your flights
```shell
python3 southwest.py USERNAME PASSWORD
```

**Note**: The script will check the entire party in under the same reservation, so there is no need
to create more than one instance of the script per reservation.

### Running In Docker

The application can also be run in a container using [Docker][3]. To build the image, run the following command:
```shell
docker build -f Dockerfile . -t auto-southwest-check-in
```
**Note**: Re-run the build command whenever you update the script.

To run the image, you can use a command such as:
```shell
docker run -d auto-southwest-check-in ARGS
# See above for the arguments that can be passed in
```
**Note**: The recommended restart policy for the container is `on-failed` or `no`

## Configuration
To set up a configuration file, copy `config.example.json` to `config.json`.

**Note**: If you are using Docker, make sure to rebuild the container after editing the configuration
file for your changes to be applied.

### Notifications
#### Notification URLs
Users can be notified on successful and failed check-ins. This is done through the [Apprise library][4].
To start, first gather the service url you want to send notifications to (information on how to create
service urls can be found on the [Apprise Readme][5]). Then put it in your configuration file.
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

### Retrieval Interval
If you provide login credentials to the script, you can choose how often the script checks for new flights
(in hours).
```json
{
    "retrieval_interval": 24
}
```

[0]: https://www.python.org/downloads/
[1]: https://pip.pypa.io/en/stable/installation/
[2]: https://www.google.com/chrome/
[3]: https://www.docker.com/
[4]: https://github.com/caronc/apprise
[5]: https://github.com/caronc/apprise#supported-notifications
