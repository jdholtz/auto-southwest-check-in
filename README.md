## Auto-Southwest Check-In
A Python script that automatically checks you in to your Southwest flight. Additionally,
the script can notify you if the price of your flight drops before departure
(see [Fare Check](CONFIGURATION.md#fare-check)).

This script can also log in to your Southwest account and automatically schedule check-ins as
flights are scheduled.

**Note**: If you are checking into an international flight, make sure to fill out all the passport
information beforehand.

## Table of Contents
- [Installation](#installation)
    * [Prerequisites](#prerequisites)
    * [Upgrading](#upgrading)
- [Using the Script](#using-the-script)
    * [Running in Docker](#running-in-docker)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [FAQ](#faq)

## Installation

### Prerequisites
- [Python 3.8+][0]
- [Pip][1]
- [Any Chromium-based browser][2]

First, download the script onto your computer
```shell
git clone https://github.com/jdholtz/auto-southwest-check-in.git
cd auto-southwest-check-in
```
Then, install the needed packages for the script
```shell
pip install -r requirements.txt
```
You may want to install the requirements in a [Python virtual environment][3] to ensure they don't conflict
with other Python projects on your system.

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

## Using the Script
To schedule a check-in, run the following command:
```shell
python3 southwest.py CONFIRMATION_NUMBER FIRST_NAME LAST_NAME
```
Alternatively, you can log in to your account, which will automatically check you in to all of your flights
```shell
python3 southwest.py USERNAME PASSWORD
```
**Note**: If any arguments contain special characters, make sure to escape them so they are passed into
the script correctly.

For the full usage of the script, run:
```shell
python3 southwest.py --help
```

If you want the latest features of the script, you can use the `develop` branch (documented changes
can be viewed in the Changelog). However, keep in mind that changes to this branch do not ensure reliability.

### Running in Docker
The application can also be run in a container using [Docker][4]. The Docker repository for this project
can be found [here][5]. To pull the latest image, run:
```shell
docker pull jdholtz/auto-southwest-check-in
```
To download a specific version, append `:vX.X` to the end of the image name. You can also append the
`:develop` tag instead to use the latest development version.

To run the image, you can use a command such as:
```shell
docker run -d jdholtz/auto-southwest-check-in CONFIRMATION_NUMBER FIRST_NAME LAST_NAME
```
or
```shell
docker run -d jdholtz/auto-southwest-check-in USERNAME PASSWORD
```
Additional arguments for the script can be passed in after the image name.

You can optionally attach a configuration file to the container by adding the
`--volume /full-path/to/config.json:/app/config.json` flag before the image name.

**Note**: The recommended restart policy for the container is `on-failure` or `no`

#### Docker Compose Example
```yaml
services:
  auto-southwest:
    image: jdholtz/auto-southwest-check-in
    container_name: auto-southwest
    restart: on-failure
    volumes:
      - /full-path/to/config.json:/app/config.json
```

Additional information on the Docker container can be found in the [public repository][5].

## Configuration
To use the default configuration file, copy `config.example.json` to `config.json`.

For information on how to set up the configuration, see [Configuration.md](CONFIGURATION.md)

## Troubleshooting
To troubleshoot a problem, run the script with the `--verbose` flag. This will display debug messages so you can
get a better overview of the problem.

If you run into any issues, please file it via [GitHub Issues][6]. Please attach any relevant logs (found in
`logs/auto-southwest-check-in.log`) to the issue. The logs should not have any personal information but check to make
sure before attaching it.

For any common questions or issues, visit the [FAQ](#faq). If you have any additional questions or discussion topics,
you can start a [GitHub Discussion][7].

## Contributing
Contributions are always welcome. Please read [Contributing.md](CONTRIBUTING.md) if you are considering making contributions.

## FAQ
Below, a list of answers to frequently asked questions about Auto-Southwest Check-In can be found. If you believe any more
questions should be added to this list, please submit a [Discussion][7] or [Pull Request][8] so the addition can be made.

<details>
<summary>Do I Need to Set up a Different Instance of the Script for Each Passenger on My Reservation?</summary>

This script will check the entire party in under the same reservation, so there is no need to create more than one instance
of the script per reservation.

However, this is not the case if you have a companion attached to your reservation. See the next question for information on
checking in a companion.
</details>

<details>
<summary>Will This Script Also Check in the Companion Attached to My Reservation?</summary>

Unfortunately, this is not possible due to how Southwest's companion system works. To ensure your companion is also checked in,
you can set up their reservation or account separately in the configuration file.
</details>

<details>
<summary>While Attempting to Run This Script, I Get a [SSL: CERTIFICATE_VERIFY_FAILED] Error. How Can I Fix It?</summary>

If you are on MacOS, this error most likely occurred because your Python installation does not have any root certificates. To
install these certificates, follow the directions found at [this Stack Overflow question][9].

Credit to [@greennayr](https://github.com/greennayr) for the answer to this question.
</details>

<details>
<summary>Script Is Stuck on 'Starting webdriver for current session' When Running in Docker. How Can I Fix It?</summary>

The current workaround is to run the Docker container with the `--privileged` flag
(see [the comment on #96](https://github.com/jdholtz/auto-southwest-check-in/issues/96#issuecomment-1587779388)). However, this
is not a very good solution. If anyone figures out a better solution, please let me know and I can make the change.
</details>


[0]: https://www.python.org/downloads/
[1]: https://pip.pypa.io/en/stable/installation/
[2]: https://en.wikipedia.org/wiki/Chromium_(web_browser)#Active
[3]: https://virtualenv.pypa.io/en/stable/
[4]: https://www.docker.com/
[5]: https://hub.docker.com/repository/docker/jdholtz/auto-southwest-check-in
[6]: https://github.com/jdholtz/auto-southwest-check-in/issues/new/choose
[7]: https://github.com/jdholtz/auto-southwest-check-in/discussions/new/choose
[8]: https://github.com/jdholtz/auto-southwest-check-in/pulls
[9]: https://stackoverflow.com/questions/42098126/mac-osx-python-ssl-sslerror-ssl-certificate-verify-failed-certificate-verify
