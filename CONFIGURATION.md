# Configuration
This guide contains all the information you need to configure Auto-Southwest Check-In to your needs. A default/example configuration
file can be found at [config.example.json](config.example.json)

## Table of Contents
- [Notifications](#notifications)
    * [Notification URLS](#notification-urls)
    * [Notification Level](#notification-level)
    * [Test The Notifications](#test-the-notifications)
- [Chrome Version](#chrome-version)
- [Retrieval Interval](#retrieval-interval)
- [Accounts](#accounts)
- [Flights](#flights)

## Notifications
### Notification URLs
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
You can also select the level of notifications you want to receive.
```json
{
  "notification_level": 1
}
```
Level 1 means you receive successful scheduling and check-in messages and all messages in later levels.\
Level 2 means you receive only error messages (failed scheduling and check-ins).

### Test The Notifications
To test if the notification URLs work, you can run the following command
```shell
$ python3 southwest.py --test-notifications
```

## Chrome Version
You can specify a specific version of Google Chrome for the script to use (only the main version - e.g. 108, 109, etc.).
This is highly recommended if you don't want to continuously keep Google Chrome on the latest version.
```json
{
    "chrome_version": 110
}
```

## Retrieval Interval
If you provide login credentials to the script, you can choose how often the script checks for new flights
(in hours).
```json
{
    "retrieval_interval": 24
}
```

## Accounts
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

## Flights
Similar to [Accounts](#accounts), you can also add more flights to the script, allowing you check in to multiple flights in the same instance and/or not
provide flight information as arguments.
```json
{
    "flights": [
        {"confirmationNumber": "num1", "firstName": "John", "lastName": "Doe"},
        {"confirmationNumber": "num2", "firstName": "Jane", "lastName": "Doe"}
    ]
}
```

[0]: https://github.com/caronc/apprise
[1]: https://github.com/caronc/apprise#supported-notifications
