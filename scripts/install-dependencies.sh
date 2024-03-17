#!/usr/bin/env bash
sudo apt-get update -y && wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && sudo apt install ./google-chrome-stable_current_amd64.deb -y
pip3 install -r requirements.txt
pip3 install -r requirements.txt -r tests/requirements.txt
