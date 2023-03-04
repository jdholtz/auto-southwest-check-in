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
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

## Installation

### Prerequisites
- [Python 3.7+][0]
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

### Upgrading
When updating the script, it is important to follow the [Changelog](CHANGELOG.md) for any actions
that need to be performed.

To get the script's current version, run the following command:
```shell
$ python3 southwest.py --version
```

To update the script, simply run:
```shell
$ git pull
```

## Using The Script
To schedule a check-in, run the following command:
```shell
$ python3 southwest.py CONFIRMATION_NUMBER FIRST_NAME LAST_NAME
```
Alternatively, you can log in to your account, which will automatically check you in to all of your flights
```shell
$ python3 southwest.py USERNAME PASSWORD
```

**Note**: The script will check the entire party in under the same reservation, so there is no need
to create more than one instance of the script per reservation.

If you want the latest features of the script, you can use the `develop` branch (documented changes
can be viewed in the Changelog). However, keep in mind that changes to this branch do not ensure reliability.

### Running In Docker
The application can also be run in a container using [Docker][3]. The Docker repository for this project
can be found [here][4]. To pull the latest image, run:
```shell
$ docker pull jdholtz/auto-southwest-check-in
```
To download a specific version, append `:vX.X.X` to the end of the image name. Additionally, you can append the
`:develop` tag to use the latest development version.

To run the image, you can use a command such as:
```shell
docker run -d jdholtz/auto-southwest-check-in ARGS
```
See above for the arguments that can be passed in. You can optionally attach a configuration file to the container
by adding the `--volume /path/to/config.json:/app/config.json` flag before the image name.

**Note**: The recommended restart policy for the container is `on-failed` or `no`

## Configuration
To use the default configuration file, copy `config.example.json` to `config.json`.

For information on how to set up the configuration, see [Configuration.md](CONFIGURATION.md)

**Note**: If you are using Docker, make sure to rebuild the container after editing the configuration
file for your changes to be applied.

## Troubleshooting
To troubleshoot a problem, run the script with the `--verbose` flag. This will print all debug messages to stderr.

If you run into any issues, please file it via [GitHub Issues][5]. Please attach any relevant logs (can be found in
`logs/auto-southwest-check-in.log`) to the issue. The logs should not have any personal information but check to make
sure before attaching it).

If you have any questions or discussion topics, start a [GitHub Discussion][6].

## Contributing
Contributions are always welcome. Please read [Contributing.md](CONTRIBUTING.md) if you are considering making contributions.

[0]: https://www.python.org/downloads/
[1]: https://pip.pypa.io/en/stable/installation/
[2]: https://www.google.com/chrome/
[3]: https://www.docker.com/
[4]: https://hub.docker.com/repository/docker/jdholtz/auto-southwest-check-in
[5]: https://github.com/jdholtz/auto-southwest-check-in/issues/new/choose
[6]: https://github.com/jdholtz/auto-southwest-check-in/discussions/new/choose
