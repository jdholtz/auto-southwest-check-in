## Auto-Southwest Check-In

A web application and Python script that automatically checks you in to your Southwest flights. Features a web dashboard for managing accounts, monitoring flights, and tracking fare changes. The system also attempts seat selection based on your preferences, adapting to Southwest's assigned seating model (effective January 2026).

**Note**: If you are checking into an international flight, make sure to fill out all the passport information beforehand.

## Table of Contents
- [Features](#features)
- [Architecture](#architecture)
- [Installation](#installation)
    * [Option 1: Web App (Railway)](#option-1-web-app-railway)
    * [Option 2: Web App (Docker - Self-hosted)](#option-2-web-app-docker---self-hosted)
    * [Option 3: CLI Only](#option-3-cli-only)
- [Web App Usage](#web-app-usage)
- [CLI Usage](#cli-usage)
- [Configuration](#configuration)
    * [Environment Variables](#environment-variables)
    * [Seat Preferences](#seat-preferences)
    * [Notifications](#notifications)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [FAQ](#faq)

## Features

- **Automatic Check-In**: Checks in to flights exactly 24 hours before departure
- **Web Dashboard**: Monitor all flights, accounts, and check-in status from a browser
- **Account Monitoring**: Log in with your Southwest account to automatically track all reservations
- **Manual Reservations**: Add individual reservations by confirmation number
- **Fare Monitoring**: Checks for fare drops every 4 hours and logs price changes
- **Seat Preferences**: Configure preferred seats (letter, row) for automatic selection
- **A-List Support**: Flag accounts as A-List for automatic seat upgrades 48 hours before departure
- **Activity Log**: Full activity log with filtering by level (info/warning/error)
- **Notifications**: Send alerts via 100+ services (Telegram, Discord, Slack, email, etc.) using Apprise
- **Login Authentication**: Password-protected web interface

## Architecture

The web app runs as a single Docker container with two processes managed by supervisord:

```
┌─────────────────────────────────────────────┐
│              Docker Container               │
│                                             │
│  ┌──────────────┐    ┌──────────────────┐   │
│  │  Next.js App │    │  Python Worker   │   │
│  │  (Frontend + │◄──►│  (Check-in       │   │
│  │   API Routes)│    │   Engine)        │   │
│  └──────┬───────┘    └────────┬─────────┘   │
│         │                     │             │
│         └────────┬────────────┘             │
│                  ▼                          │
│           ┌────────────┐                    │
│           │   SQLite   │                    │
│           │  Database  │                    │
│           └────────────┘                    │
└─────────────────────────────────────────────┘
```

- **Next.js** serves the web UI and API routes on port 3000
- **Python Worker** handles check-ins, fare monitoring, and seat selection using SeleniumBase + headless Chromium
- **SQLite** stores accounts, reservations, flights, preferences, and logs

## Installation

### Option 1: Web App (Railway)

The easiest way to deploy. Railway provides container hosting with persistent storage.

1. **Fork this repository** on GitHub

2. **Create a Railway project**:
   - Go to [railway.app](https://railway.app) and create a new project
   - Select "Deploy from GitHub repo" and choose your fork
   - Railway will auto-detect the `Dockerfile` and build

3. **Add a persistent volume**:
   - In your service settings, go to **Volumes**
   - Add a volume mounted at `/app/data` (this persists your SQLite database across deploys)

4. **Set environment variables** (in the Railway **Variables** tab):
   ```
   AUTH_USERNAME=your_username
   AUTH_PASSWORD=your_secure_password
   AUTH_SECRET=a_random_secret_string
   ```

5. **Generate a public domain**:
   - Go to **Settings** > **Networking** > **Generate Domain**
   - Your app will be available at `https://your-app.up.railway.app`

6. **Access the web UI** at your Railway URL and log in

### Option 2: Web App (Docker - Self-hosted)

Run the web app on any server with Docker installed.

1. **Clone the repository**:
   ```shell
   git clone https://github.com/jdholtz/auto-southwest-check-in.git
   cd auto-southwest-check-in
   ```

2. **Build the Docker image**:
   ```shell
   docker build -t sw-checkin .
   ```

3. **Run the container**:
   ```shell
   docker run -d \
     --name sw-checkin \
     -p 3000:3000 \
     -v sw-checkin-data:/app/data \
     -e AUTH_USERNAME=admin \
     -e AUTH_PASSWORD=your_secure_password \
     -e AUTH_SECRET=your_random_secret \
     --restart on-failure \
     sw-checkin
   ```

4. **Access the web UI** at `http://localhost:3000`

#### Docker Compose (Web App)
```yaml
services:
  sw-checkin:
    build: .
    container_name: sw-checkin
    restart: on-failure
    ports:
      - "3000:3000"
    volumes:
      - sw-checkin-data:/app/data
    environment:
      - AUTH_USERNAME=admin
      - AUTH_PASSWORD=your_secure_password
      - AUTH_SECRET=your_random_secret

volumes:
  sw-checkin-data:
```

### Option 3: CLI Only

Use the original command-line interface without the web dashboard.

#### Prerequisites
- [Python 3.9+]
- [Pip]
- [Any Chromium-based browser]

#### Setup
```shell
git clone https://github.com/jdholtz/auto-southwest-check-in.git
cd auto-southwest-check-in
pip3 install -r requirements.txt
```

#### Run
```shell
# Check in by confirmation number
python3 southwest.py CONFIRMATION_NUMBER FIRST_NAME LAST_NAME

# Or log in to monitor all flights
python3 southwest.py USERNAME PASSWORD
```

#### CLI Docker
```shell
docker build -f Dockerfile.cli -t sw-checkin-cli .
docker run -d sw-checkin-cli CONFIRMATION_NUMBER FIRST_NAME LAST_NAME
```

## Web App Usage

### Dashboard (`/`)
Overview of your check-in system:
- Stats cards: active accounts, reservations, upcoming check-ins, success/fail counts
- Upcoming check-ins with live countdown timers
- Recent activity feed

### Accounts (`/accounts`)
Manage your Southwest accounts:
- Add accounts with username and password
- Toggle **A-List** status for accounts with A-List or A-List Preferred membership
- Enable **Auto Seat Upgrade** to attempt preferred seat selection 48 hours before departure
- Enable/disable account monitoring

### Reservations (`/reservations`)
Track all reservations:
- Reservations are auto-discovered when accounts are monitored
- Add manual reservations by confirmation number + passenger name
- Expand to see flights with departure times, check-in countdowns, and status

### Flights (`/flights`)
Monitor all tracked flights:
- Flight number, route, departure time, check-in countdown
- Assigned seat (after check-in or seat selection)
- Status: pending, scheduled, checking_in, success, failed
- Click a flight to view worker logs

### Activity (`/activity`)
Full activity log:
- Filter by level: All, Info, Warning, Error
- Shows worker actions: account processing, reservation retrieval, check-ins, fare checks, seat upgrades
- Pagination with load more

### Settings (`/settings`)
Configure preferences:
- **Seat Preferences**: Choose preferred seat letters (A-F), preferred rows, and fallback letters
- **Notifications**: Add notification service URLs using [Apprise format](https://github.com/caronc/apprise#supported-notifications)

## CLI Usage

For the full usage of the CLI script, run:
```shell
python3 southwest.py --help
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AUTH_USERNAME` | Web UI login username | `admin` |
| `AUTH_PASSWORD` | Web UI login password | `admin` |
| `AUTH_SECRET` | Secret key for signing auth tokens | `change-me-in-production` |
| `DB_PATH` | Path to SQLite database file | `/app/data/checkin.db` |

**Important**: Change the default credentials before deploying to production.

### Seat Preferences

Southwest uses assigned seating (effective January 27, 2026). Configure your preferences in the Settings page:

- **Preferred Letters**: Seat letters to target first (e.g., A, F for window seats)
- **Preferred Rows**: Row numbers where preferred letters are prioritized (e.g., 1-6 for front rows)
- **Fallback Letters**: Alternative seat letters if preferred seats are unavailable (e.g., A, C, D, F for aisle/window)

For **A-List members**: Enable "Auto Seat Upgrade" on your account to attempt upgrading to Extra Legroom or Preferred seats 48 hours before departure.

### Notifications

Add notification URLs in Settings using [Apprise URL format](https://github.com/caronc/apprise#supported-notifications). Examples:

| Service | URL Format |
|---------|------------|
| Telegram | `tgram://BotToken/ChatID` |
| Discord | `discord://WebhookID/WebhookToken` |
| Slack | `slack://TokenA/TokenB/TokenC/Channel` |
| Email (SMTP) | `mailto://user:pass@gmail.com` |
| Pushover | `pover://user@token` |

## Troubleshooting

### Web App
- Check the **Activity** page for worker logs and errors
- If the dashboard shows all 0s, ensure the worker process is running (check Railway deploy logs)
- If login fails, verify your `AUTH_USERNAME` and `AUTH_PASSWORD` environment variables
- For database issues, ensure the `/app/data` volume is properly mounted

### CLI
To troubleshoot the CLI, run with the `--verbose` flag for debug messages, or `--debug-screenshots` for browser screenshots (stored in `logs/`).

If you run into any issues, please file it via [GitHub Issues]. Please attach any relevant logs (found in `logs/auto-southwest-check-in.log`) to the issue.

For common questions, visit the [FAQ](#faq). For discussions, start a [GitHub Discussion].

## Contributing
Contributions are always welcome. Please read [Contributing.md](CONTRIBUTING.md) if you are considering making contributions.

## FAQ

<details>
<summary>Do I Need to Set up a Different Instance for Each Passenger on My Reservation?</summary>

This script will check the entire party in under the same reservation, so there is no need to create more than one instance per reservation.

However, this is not the case if you have a companion attached to your reservation. See the next question for information on checking in a companion.
</details>

<details>
<summary>Will This Script Also Check in the Companion Attached to My Reservation?</summary>

Unfortunately, this is not possible due to how Southwest's companion system works. To ensure your companion is also checked in, you can add their reservation or account separately.
</details>

<details>
<summary>How Does the Seat Selection Work with Southwest's New Assigned Seating?</summary>

Southwest switched from open seating to assigned seats on January 27, 2026. The app adapts to this:

- **At check-in (24h before)**: The app checks in and logs the seat assignment from the API response
- **For A-List members (48h before)**: If "Auto Seat Upgrade" is enabled, the app attempts to select/upgrade your seat based on your preferences
- **Seat preferences**: Configure preferred seat letters and rows in Settings

The seat selection feature uses a progressive discovery approach to work with Southwest's API, logging response structures to help refine the selection logic over time.
</details>

<details>
<summary>What Is the Difference Between the Web App and the CLI?</summary>

The **Web App** provides a browser-based dashboard, persistent database, automatic account monitoring, fare checking, and seat management. It runs continuously on a server.

The **CLI** is the original command-line script. It runs on your local machine and exits after check-in completes. Use the CLI if you just need a quick one-time check-in.
</details>

<details>
<summary>I Get a [SSL: CERTIFICATE_VERIFY_FAILED] Error. How Can I Fix It?</summary>

If you are on MacOS, this error most likely occurred because your Python installation does not have any root certificates. To install these certificates, follow the directions found at [this Stack Overflow question].
</details>

<details>
<summary>The Script Is Stuck on 'Starting webdriver for current session'. How Can I Fix It?</summary>

Depending on your network speed or compute power, it may take 3 to 5 minutes to start the browser and load the Southwest website. If you are still running into this issue after 8+ minutes, please file an [issue][GitHub Issues].

If running Docker, the current workaround is to run with the `--privileged` flag (see [the comment on #96]).
</details>


[Python 3.9+]: https://www.python.org/downloads/
[Pip]: https://pip.pypa.io/en/stable/installation/
[Any Chromium-based browser]: https://en.wikipedia.org/wiki/Chromium_(web_browser)#Browsers_based_on_Chromium
[Python virtual environment]: https://virtualenv.pypa.io/en/stable/
[Docker]: https://www.docker.com/
[Docker repository]: https://hub.docker.com/repository/docker/jdholtz/auto-southwest-check-in
[GitHub Issues]: https://github.com/jdholtz/auto-southwest-check-in/issues/new/choose
[GitHub Discussion]: https://github.com/jdholtz/auto-southwest-check-in/discussions/new/choose
[Pull Request]: https://github.com/jdholtz/auto-southwest-check-in/pulls
[this Stack Overflow question]: https://stackoverflow.com/questions/42098126/mac-osx-python-ssl-sslerror-ssl-certificate-verify-failed-certificate-verify
[the comment on #96]: https://github.com/jdholtz/auto-southwest-check-in/issues/96#issuecomment-1587779388
