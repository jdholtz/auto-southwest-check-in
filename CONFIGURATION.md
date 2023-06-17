# Configuration
This guide contains all the information you need to configure Auto-Southwest Check-In to your needs. A default/example configuration
file can be found at [config.example.json](config.example.json)

## Table of Contents
- [Fare Check](#fare-check)
- [Notifications](#notifications)
    * [Notification URLS](#notification-urls)
    * [Notification Level](#notification-level)
    * [Test The Notifications](#test-the-notifications)
- [Chrome Version](#chrome-version)
- [Chromedriver Path](#chromedriver-path)
- [Retrieval Interval](#retrieval-interval)
- [Accounts](#accounts)
- [Reservations](#reservations)

## Fare Check
Default: false \
Type: Boolean

In addition to automatically checking in, check for price drops on an interval
(see [Retrieval Interval](#retrieval-interval)). If a lower fare is found, the user will be notified.

**Note**: Companion passes are not supported for fare checking.
```json
{
    "check_fares": true
}
```

## Notifications
### Notification URLs
Default: [] \
Type: String or List

Users can be notified on successful and failed check-ins. This is done through the [Apprise library][0].
To start, first gather the service URL you want to send notifications to (information on how to create
service URLs can be found on the [Apprise Readme][1]). Then put it in your configuration file.
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

### Notification Level
Default: 1 \
Type: Integer

You can also select the level of notifications you want to receive.
```json
{
  "notification_level": 1
}
```
Level 1 means you receive successful scheduling and check-in messages, lower fare messages, and all messages in later levels.\
Level 2 means you receive only error messages (failed scheduling and check-ins).

### Test The Notifications
To test if the notification URLs work, you can run the following command
```shell
$ python3 southwest.py --test-notifications
```

## Chrome Version
Default: The latest stable version \
Type: Integer

You can specify a specific version of your Chromium browser for the script to use (only the main version - e.g. 108, 109, etc.).
This is highly recommended if you don't want to continuously keep your Chromium browser on the latest version.
```json
{
    "chrome_version": 110
}
```

## Chromedriver Path
Default: The path of the Chromedriver executable downloaded by undetected_chromedriver \
Type: String

You can specify a custom path of the Chromedriver executable for the script to use.

**Note**: This should not be used in a Docker container because the Chromedriver path is set automatically.
```json
{
    "chromedriver_path": "/usr/bin/chromedriver"
}
```

## Retrieval Interval
Default: 24 hours \
Type: Integer

You can choose how often the script checks for lower fares on scheduled flights (in hours). Additionally, this
interval will also determine how often the script checks for new flights if login credentials are provided. To
disable account/fare monitoring, set this option to `0` (The account/fares will only be checked once).
```json
{
    "retrieval_interval": 24
}
```

## Accounts
Default: [] \
Type: List

You can add more accounts to the script, allowing you to run multiple accounts at the same time and/or not
provide a username and password as arguments.
```json
{
    "accounts": [
        {"username": "user1", "password": "pass1"},
        {"username": "user2", "password": "pass2"}
    ]
}
```

## Reservations
Default: [] \
Type: List

Similar to [Accounts](#accounts), you can also add more reservations to the script, allowing you check in to multiple reservations in the same instance
and/or not provide reservation information as arguments.
```json
{
    "reservations": [
        {"confirmationNumber": "num1", "firstName": "John", "lastName": "Doe"},
        {"confirmationNumber": "num2", "firstName": "Jane", "lastName": "Doe"}
    ]
}
```

[0]: https://github.com/caronc/apprise
[1]: https://github.com/caronc/apprise#supported-notifications
