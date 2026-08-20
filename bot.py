import os
import json
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime
from zoneinfo import ZoneInfo

import requests


BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

API = f"https://api.telegram.org/bot{BOT_TOKEN}"

SUBSCRIBERS_FILE = "subscribers.json"
STATE_FILE = "state.json"

IST = ZoneInfo("Asia/Kolkata")


# --------------------------------------------------
# Render health server
# --------------------------------------------------

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header(
                "Content-Type",
                "text/plain"
            )
            self.end_headers()

            self.wfile.write(
                b"Toxic Telegram bot is running"
            )

        else:
            self.send_response(200)
            self.send_header(
                "Content-Type",
                "text/plain"
            )
            self.end_headers()

            self.wfile.write(
                b"Toxic BMS Telegram Bot"
            )

    def log_message(self, format, *args):
        return


def start_health_server():

    port = int(
        os.environ.get(
            "PORT",
            "10000"
        )
    )

    server = HTTPServer(
        ("0.0.0.0", port),
        HealthHandler
    )

    print(
        f"🌐 Health server listening on port {port}"
    )

    server.serve_forever()


# --------------------------------------------------
# Subscribers
# --------------------------------------------------

def load_subscribers():

    try:

        with open(
            SUBSCRIBERS_FILE,
            "r"
        ) as f:

            return json.load(f)

    except (
        FileNotFoundError,
        json.JSONDecodeError
    ):

        return []


def save_subscribers(subscribers):

    with open(
        SUBSCRIBERS_FILE,
        "w"
    ) as f:

        json.dump(
            subscribers,
            f,
            indent=2
        )


# --------------------------------------------------
# BMS state
# --------------------------------------------------

def load_state():

    try:

        with open(
            STATE_FILE,
            "r"
        ) as f:

            return json.load(f)

    except (
        FileNotFoundError,
        json.JSONDecodeError
    ):

        return {
            "available": False,
            "last_checked": None,
            "venues": {}
        }


# --------------------------------------------------
# Telegram
# --------------------------------------------------

def send_message(
    chat_id,
    text
):

    try:

        response = requests.post(
            f"{API}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": False
            },
            timeout=20
        )

        if response.status_code != 200:

            print(
                f"Failed to send to {chat_id}: "
                f"{response.text}"
            )

        return (
            response.status_code == 200
        )

    except Exception as e:

        print(
            f"Telegram error for {chat_id}: {e}"
        )

        return False


# --------------------------------------------------
# Status message
# --------------------------------------------------

def status_message():

    state = load_state()

    venues = state.get(
        "venues",
        {}
    )

    urbl = venues.get(
        "URBL",
        False
    )

    vccb = venues.get(
        "VCCB",
        False
    )

    pvoo = venues.get(
        "PVOO",
        False
    )

    last_checked = state.get(
        "last_checked"
    )

    if last_checked:

        try:

            dt = datetime.fromtimestamp(
                last_checked,
                tz=IST
            )

            checked = dt.strftime(
                "%d-%m-%Y %I:%M:%S %p IST"
            )

        except Exception:

            checked = "Unknown"

    else:

        checked = "No check recorded yet"

    return (
        "🎬 Toxic BMS Watcher\n\n"

        "📅 26 August 2026\n\n"

        f"{'🚨' if urbl else '❌'} "
        f"Urvashi Cinema — "
        f"{'BOOKING OPEN' if urbl else 'Not released'}\n"

        f"{'🚨' if vccb else '❌'} "
        f"Victory Cinema — "
        f"{'BOOKING OPEN' if vccb else 'Not released'}\n"

        f"{'🚨' if pvoo else '❌'} "
        f"PVR Orion Mall — "
        f"{'BOOKING OPEN' if pvoo else 'Not released'}\n\n"

        f"🕐 Last BMS check: {checked}\n"

        "🔄 BMS checks: approximately every minute\n\n"

        "/status — Check current status\n"
        "/stop — Stop notifications"
    )


# --------------------------------------------------
# Handle Telegram commands
# --------------------------------------------------

def handle_update(update):

    message = update.get(
        "message"
    )

    if not message:
        return

    text = message.get(
        "text",
        ""
    ).strip()

    chat = message.get(
        "chat",
        {}
    )

    chat_id = chat.get(
        "id"
    )

    if not chat_id:
        return

    subscribers = load_subscribers()

    # /start
    if text.startswith("/start"):

        if chat_id not in subscribers:

            subscribers.append(
                chat_id
            )

            save_subscribers(
                subscribers
            )

        send_message(
            chat_id,
            "✅ You are subscribed to "
            "Toxic BMS alerts!\n\n"
            + status_message()
        )

        print(
            f"Subscribed: {chat_id}"
        )

    # /status
    elif text.startswith("/status"):

        send_message(
            chat_id,
            status_message()
        )

        print(
            f"Status requested: {chat_id}"
        )

    # /stop
    elif text.startswith("/stop"):

        if chat_id in subscribers:

            subscribers.remove(
                chat_id
            )

            save_subscribers(
                subscribers
            )

        send_message(
            chat_id,
            "🔕 You have been unsubscribed.\n\n"
            "Send /start whenever you want "
            "to subscribe again."
        )

        print(
            f"Unsubscribed: {chat_id}"
        )


# --------------------------------------------------
# Telegram polling
# --------------------------------------------------

def poll_updates(offset=None):

    params = {
        "timeout": 30
    }

    if offset is not None:

        params["offset"] = offset

    try:

        response = requests.get(
            f"{API}/getUpdates",
            params=params,
            timeout=40
        )

        response.raise_for_status()

        data = response.json()

        if not data.get("ok"):

            print(
                "Telegram API error:",
                data
            )

            return offset

        for update in data.get(
            "result",
            []
        ):

            offset = (
                update["update_id"] + 1
            )

            handle_update(
                update
            )

    except Exception as e:

        print(
            "Polling error:",
            e
        )

        time.sleep(5)

    return offset


# --------------------------------------------------
# Main
# --------------------------------------------------

def main():

    print(
        "🤖 Toxic Telegram bot started"
    )

    print(
        "Listening for /start, "
        "/status and /stop"
    )

    # Start Render HTTP server
    threading.Thread(
        target=start_health_server,
        daemon=True
    ).start()

    offset = None

    while True:

        offset = poll_updates(
            offset
        )


if __name__ == "__main__":

    main()
