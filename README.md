## Auto-Southwest Check-In
Running this script will automatically check you into your flight 24 hours before your flight

WARNING: Until a way has been found to automatically generate a header, \
you will need to get the `X-Dublriiu-E` header and put it in the `reservation.py` \
file to successfuly check in. A way to get the header is to proxy the IOS app and \
grab the header from the proxy. I'm not sure how long this header is valid for.
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