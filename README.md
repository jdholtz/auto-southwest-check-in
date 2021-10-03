## Auto-Southwest Check-In
Running this script will automatically check you into your flight 24 hours before your flight

## Dependencies
- [Python][0] (Any version of Python 2 or 3 works)
- [Pip][1]

## Download
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
$ python3 checkin.py CONFIRMATION_NUMBER FIRST_NAME LAST_NAME
```

[0]: https://www.python.org/downloads/
[1]: https://pip.pypa.io/en/stable/installation/