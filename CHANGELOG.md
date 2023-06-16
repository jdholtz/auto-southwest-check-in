# Changelog
When upgrading to a new version, make sure to follow the directions under the "Upgrading" header of the corresponding version.
If there is no "Upgrading" header for that version, no post-upgrade actions need to be performed.

## Upcoming

### New Features
- This project is now licensed under the GPLv3 license instead of the MIT
license
- Automatically handle flight changes and cancellations
([#103](https://github.com/jdholtz/auto-southwest-check-in/pull/103))

### Improvements
- Don't send lower fare notifications when the price difference is only -1 USD
    - This is a false positive. Refer to
    [#102](https://github.com/jdholtz/auto-southwest-check-in/discussions/102)
    for more information


## 4.1 (2023-06-04)

### Improvements
- Make the webdriver initialization more resistant to random issues
([#89](https://github.com/jdholtz/auto-southwest-check-in/issues/89) and
[#90](https://github.com/jdholtz/auto-southwest-check-in/issues/90))
- Skip flight retrieval when a bad request is encountered. Previously,
the script would exit

### Bug Fixes
- Handle cases where no fares are available for a flight
([#86](https://github.com/jdholtz/auto-southwest-check-in/issues/86))
- Ensure the correct flight's fares are checked
([#92](https://github.com/jdholtz/auto-southwest-check-in/issues/92))


## 4.0 (2023-05-06)

### New features
- Add fare checker ([#73](https://github.com/jdholtz/auto-southwest-check-in/pull/73))
    - Improvements and fixes by [@fusionneo](https://github.com/fusionneo)
    - This is currently in beta testing and can be enabled with the
    [check_fares](CONFIGURATION.md#fare-check) configuration option

### Improvements
- Improve webdriver speed and reliability
([#76](https://github.com/jdholtz/auto-southwest-check-in/pull/76)
by [@fusionneo](https://github.com/fusionneo))

### Bug Fixes
- Remove the user agent header for the webdriver
([#58](https://github.com/jdholtz/auto-southwest-check-in/issues/58) and
[#80](https://github.com/jdholtz/auto-southwest-check-in/issues/80))

### Upgrading
Upgrade the dependencies to the latest versions by running `pip install -r requirements.txt`


## 3.1 (2023-03-25)

### New features
- Users can now specify a custom path to a Chromedriver executable
([#65](https://github.com/jdholtz/auto-southwest-check-in/pull/65))
- All Chromium-based browsers are now officially supported
- Docker image optimizations ([#65](https://github.com/jdholtz/auto-southwest-check-in/pull/65)):
    - Official ARM support ([#27](https://github.com/jdholtz/auto-southwest-check-in/issues/27))
    - Alpine Linux is now used, reducing image size by 40%


## 3.0 (2023-03-10)

### New features
- A logger was added to enable better troubleshooting for both users and developers
([#47](https://github.com/jdholtz/auto-southwest-check-in/pull/47))
- A verbosity flag can be specified (`--verbose` or `-v`) to print debug messages to stderr. Shorthand
for `--version` flag is now `-V` ([#47](https://github.com/jdholtz/auto-southwest-check-in/pull/47))
- Account monitoring can now be disabled by providing a value of `0` to the `retrieval_interval`
configuration option (The account will only be checked once)
- The Docker image is now available in the public repository. See the `Running in Docker` section of the
Readme for more details ([#55](https://github.com/jdholtz/auto-southwest-check-in/pull/55))

### Bug Fixes
- Sleep time no longer overflows for flights very far into the future
([#50](https://github.com/jdholtz/auto-southwest-check-in/pull/50))
- Only attempt to schedule reservations that are flights
([#53](https://github.com/jdholtz/auto-southwest-check-in/pull/53)
by [@samdatkins](https://github.com/samdatkins))

### Upgrading
Upgrade the dependencies to the latest versions by running `pip install -r requirements.txt`


## 2.0 (2023-02-13)

### New features
- A `--help` flag was added to display information on how to use the script
- Added official Python 3.11 support
- A [Configuration](CONFIGURATION.md) guide was written to facilitate the script's configuration
- Allow multiple accounts/flights to be run in one instance of the script ([#33](https://github.com/jdholtz/auto-southwest-check-in/pull/33))
- A [Contributing](CONTRIBUTING.md) document was added to provide potential contributors with a guide on
how they can help with the project.
- Allow users to specify a specific Google Chrome version to use ([#40](https://github.com/jdholtz/auto-southwest-check-in/pull/40))

### Improvements
- Optimized the script's entrypoint so the user is no longer required to install the requirements (besides Python)
to use the `--version` and `--help` flags. This also makes responses for those flags instantaneous

### Upgrading
Upgrade the dependencies to the latest versions by running `pip install -r requirements.txt`


## 1.0 (2022-12-10)

### New Features
- Many internal changes were done to improve the codebase, making the execution flow much more practical
(Thanks to [@sdstolworthy](https://github.com/sdstolworthy) for the
[proposed refactors](https://github.com/jdholtz/auto-southwest-check-in/issues/10#issuecomment-1292725481))
- If login credentials are provided, the script will continuously monitor the account for new flights, scheduling
check-ins automatically (Fixes [#10](https://github.com/jdholtz/auto-southwest-check-in/issues/10)).
The interval can be modified with the
[retrieval_interval](https://github.com/jdholtz/auto-southwest-check-in/tree/master#retrieval-interval) config option
- The version of the script can now be retrieved with the `--version` or `-v` flag

### Upgrading
Upgrade the dependencies to the latest versions by running `pip install --upgrade -r requirements.txt`
