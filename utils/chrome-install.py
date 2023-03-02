#!/usr/bin/env python3
"""Chrome installation script for the docker image"""

import os
import requests

# Get configured major chrome_version
chrome_version = os.getenv('CHROME_VERSION', None)

def get_default_version(data):
    return data['versions'][0]

def get_chrome_version_to_install():
    response = requests.get('https://versionhistory.googleapis.com/v1/chrome/platforms/linux/channels/stable/versions')
    if response.status_code == 200:
        data = response.json()

        # If the config file does not have the chrome_version specified, return default
        if chrome_version is None:
            return get_default_version(data)
        
        # Iterate through the list of versions until we find the latest minor/patch version for the major version we're looking for
        for version in data['versions']:
            if version['version'].startswith(f'{chrome_version}.'):
                return version['version']
            
        # If we did not find a match, return default
        return get_default_version(data)
    else:
        print(f'Request failed with status code {response.status_code}')

def setup():
    version = get_chrome_version_to_install()
    os.system(f"wget --no-verbose -O /tmp/chrome.deb https://dl.google.com/linux/chrome/deb/pool/main/g/google-chrome-stable/google-chrome-stable_{version}-1_amd64.deb && apt install -y /tmp/chrome.deb && rm /tmp/chrome.deb")

setup()