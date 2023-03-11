#!/bin/bash

# The Chrome version is set as an environment variable so it can be automatically
# read inside the script. This makes it so users don't have to provide the 'chrome_version'
# option in the config.json
_CHROME_VERSION=$(google-chrome-stable --version | awk -F '[ .]' '{print $3}') python3 southwest.py "$@"
