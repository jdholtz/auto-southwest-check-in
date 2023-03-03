# Changelog
When upgrading to a new version, make sure to follow the directions under the "Upgrading" header of the corresponding version.
If there is no "Upgrading" header for that version, no post-upgrade actions need to be performed.


## Upcoming

### New features
- A logger was added to enable better troubleshooting for both users and developers
([#47](https://github.com/jdholtz/auto-southwest-check-in/pull/47))
- A verbosity flag can be specified (`--verbose` or `-v`) to print debug messages to stderr. Shorthand
for `--version` flag is now `-V` ([#47](https://github.com/jdholtz/auto-southwest-check-in/pull/47))
- Account monitoring can now be disabled by providing a value of `0` to the `retrieval_interval`
configuration option (The account will only be checked once)

### Bug Fixes
- Sleep time no longer overflows for flights very far into the future
([#50](https://github.com/jdholtz/auto-southwest-check-in/pull/50))
- Only attempt to schedule reservations that are flights
([#53](https://github.com/jdholtz/auto-southwest-check-in/pull/53)
by [@samdatkins](https://github.com/samdatkins))


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
