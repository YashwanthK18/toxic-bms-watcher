# 🎬 Toxic BMS Ticket Watcher

A lightweight BookMyShow ticket-release monitor for **Toxic: A Fairy Tale for Grown-ups**.

The watcher checks BookMyShow for the selected date and theatres, runs automatically through GitHub Actions, and sends notifications through Telegram when bookings open.

## 🎯 Current Configuration

**Movie:** Toxic: A Fairy Tale for Grown-ups
**BookMyShow Event ID:** `ET00378770`
**Target date:** 26 August 2026
**City:** Bengaluru

### Target Theatres

| Code   | Theatre        |
| ------ | -------------- |
| `URBL` | Urvashi Cinema |
| `VCCB` | Victory Cinema |
| `PVOO` | PVR Orion Mall |

## 🔔 Notifications

The watcher provides two types of Telegram notifications.

### Booking alert

When any monitored theatre becomes bookable:

> 🚨 TOXIC BOOKINGS OPEN!
>
> 🎬 Toxic: A Fairy Tale for Grown-ups
>
> 📅 26-08-2026
>
> ✅ Booking available at:
>
> * Urvashi Cinema
>
> 🎟️ Book now: BMS booking page

The booking alert is sent when the detector changes from unavailable to available.

### Status update

Every 10 minutes, the bot sends a heartbeat showing the current status of all monitored theatres:

```text
🔎 Toxic BMS Status

🎬 Toxic: A Fairy Tale for Grown-ups
📅 26-08-2026

❌ Not released — Urvashi Cinema
❌ Not released — Victory Cinema
❌ Not released — PVR Orion Mall

🕐 Checked: 10:40 PM
🔄 Next check: ~1 minute
```

The BMS check itself is performed approximately once per minute.

## 🏗️ Architecture

```text
                 cron-job.org
                      │
                      │ Every minute
                      ▼
              GitHub Actions
                      │
                      ▼
                 poller.py
                      │
                      ▼
                ScraperAPI
                India proxy
                      │
                      ▼
                 BookMyShow
                      │
          ┌───────────┼───────────┐
          ▼           ▼           ▼
        URBL        VCCB        PVOO
       Urvashi     Victory     PVR Orion
          │           │           │
          └───────────┼───────────┘
                      ▼
                Booking open?
                  /       \
                NO         YES
                │           │
                ▼           ▼
          Continue      Telegram
          monitoring     alert
```

## 📁 Project Structure

```text
toxic-bms-watcher/
│
├── poller.py
├── config.json
├── state.json
├── requirements.txt
├── README.md
│
└── .github/
    └── workflows/
        └── booking-watch.yml
```

## ⚙️ Configuration

The main configuration is stored in `config.json`.

Example:

```json
{
  "detector": "venue_date",
  "movie": "Toxic: A Fairy Tale for Grown-ups",
  "requested_date": "20260826",
  "venue_codes": [
    "URBL",
    "VCCB",
    "PVOO"
  ],
  "venue_label": "Urvashi Cinema / Victory Cinema / PVR Orion Mall",
  "url_template": "https://in.bookmyshow.com/movies/bengaluru/toxic-a-fairy-tale-for-grownups/buytickets/ET00378770/{date}"
}
```

## 🔐 Secrets

Sensitive credentials are **not stored in the source code**.

The following values are stored as GitHub Actions repository secrets:

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
SCRAPERAPI_KEY
```

Never commit these values to the repository.

## 📦 Dependencies

The project currently requires:

```text
requests
```

Install locally with:

```bash
pip install -r requirements.txt
```

## 🚀 Running Locally

Set the required environment variables:

```bash
export TELEGRAM_BOT_TOKEN="your_bot_token"
export TELEGRAM_CHAT_ID="your_chat_id"
export SCRAPERAPI_KEY="your_scraperapi_key"
```

Then run:

```bash
python -u poller.py
```

On Windows PowerShell:

```powershell
$env:TELEGRAM_BOT_TOKEN="your_bot_token"
$env:TELEGRAM_CHAT_ID="your_chat_id"
$env:SCRAPERAPI_KEY="your_scraperapi_key"

python -u poller.py
```

## ☁️ GitHub Actions

The workflow is located at:

```text
.github/workflows/booking-watch.yml
```

Each workflow execution performs one BMS check and then exits.

`cron-job.org` is responsible for triggering the GitHub Actions workflow approximately once per minute.

The workflow:

1. Checks out the repository.
2. Sets up Python.
3. Installs dependencies.
4. Runs `poller.py`.
5. Saves the booking state when it changes.

## ⏱️ Why cron-job.org?

GitHub Actions scheduled workflows are not intended to provide an exact every-minute scheduler.

Instead:

```text
cron-job.org
      ↓
GitHub Actions workflow_dispatch
      ↓
one BMS check
      ↓
workflow exits
      ↓
next cron execution
```

This allows the watcher to perform approximately one check per minute without keeping a GitHub Actions runner running continuously.

## 🧠 Booking Detection

The watcher uses the configured `venue_codes` and requested date to determine whether BookMyShow has exposed a booking URL for one of the target cinemas.

The target venue codes are:

```text
URBL
VCCB
PVOO
```

The detector looks for the corresponding venue/date booking pattern.

For example:

```text
/URBL/20260826
```

indicates that the Urvashi Cinema target is available.

## 💾 State Tracking

`state.json` stores the previous availability state.

Example:

```json
{
  "available": false
}
```

This prevents repeated booking notifications when the availability state has not changed.

The important transition is:

```text
False → True
```

which triggers the booking notification.

## 🛡️ Security

Do not commit:

* Telegram bot tokens
* GitHub personal access tokens
* ScraperAPI keys
* Any other private credentials

GitHub repository secrets should be used for sensitive values.

If a credential is accidentally exposed, revoke it immediately and create a replacement.

## 🧪 Monitoring

To verify that the system is running:

### cron-job.org

Check the execution history for:

```text
Toxic BMS Watcher
```

Successful GitHub workflow-dispatch requests normally return:

```text
204 No Content
```

### GitHub Actions

Go to:

```text
Actions → Toxic BMS Booking Watch
```

The `Check BMS` step should show output similar to:

```text
[Toxic: A Fairy Tale for Grown-ups @ 20260826]
available=False (was False)
```

When bookings open, it should transition to:

```text
available=True (was False)
```

and send the Telegram alert.

## 📱 Telegram

The Telegram bot is used for:

* Booking-open alerts
* 10-minute heartbeat/status updates
* Monitoring confirmation

The bot token is kept exclusively in GitHub Secrets.

## ⚠️ Limitations

BookMyShow may change its website structure, internal APIs, booking URLs, or anti-bot protections at any time.

Therefore, this project is intended as a personal monitoring tool rather than a guaranteed BookMyShow API integration.

The watcher detects the availability state exposed by the monitored BookMyShow pages. It does not guarantee that seats will remain available after the notification is received.

## 📄 License

This project is intended for personal use.

Use responsibly and respect BookMyShow's terms of service and applicable rate limits.
