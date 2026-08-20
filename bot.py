import os
import json
import time
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

API = f"https://api.telegram.org/bot{BOT_TOKEN}"

SUBSCRIBERS_FILE = "subscribers.json"
STATE_FILE = "state.json"

IST = ZoneInfo("Asia/Kolkata")


def load_subscribers():
    try:
        with open(SUBSCRIBERS_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_subscribers(subscribers):
    with open(SUBSCRIBERS_FILE, "w") as f:
        json.dump(subscribers, f, indent=2)


def load_state():
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "available": False,
            "last_checked": None,
            "venues": {}
        }


def send_message(chat_id, text):
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

        return response.status_code == 200

    except Exception as e:
        print(
            f"Telegram error for {chat_id}: {e}"
        )
        return False


def status_message():
    state = load_state()

    venues = state.get("venues", {})

    urbl = venues.get("URBL", False)
    vccb = venues.get("VCCB", False)
    pvoo = venues.get("PVOO", False)

    last_checked = state.get("last_checked")

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


def handle_update(update):
    message = update.get("message")

    if not message:
        return

    text = message.get("text", "").strip()

    chat = message.get("chat", {})
    chat_id = chat.get("id")

    if not chat_id:
        return

    subscribers = load_subscribers()

    if text.startswith("/start"):

        if chat_id not in subscribers:
            subscribers.append(chat_id)
            save_subscribers(subscribers)

        send_message(
            chat_id,
            "✅ You are subscribed to Toxic BMS alerts!\n\n"
            + status_message()
        )

        print(
            f"Subscribed: {chat_id}"
        )

    elif text.startswith("/status"):

        send_message(
            chat_id,
            status_message()
        )

    elif text.startswith("/stop"):

        if chat_id in subscribers:
            subscribers.remove(chat_id)
            save_subscribers(subscribers)

        send_message(
            chat_id,
            "🔕 You have been unsubscribed.\n\n"
            "Send /start whenever you want to subscribe again."
        )

        print(
            f"Unsubscribed: {chat_id}"
        )


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

            handle_update(update)

    except Exception as e:

        print(
            "Polling error:",
            e
        )

        time.sleep(5)

    return offset


def main():

    print(
        "🤖 Toxic Telegram bot started"
    )

    print(
        "Listening for /start, /status and /stop"
    )

    offset = None

    while True:

        offset = poll_updates(
            offset
        )


if __name__ == "__main__":
    main()
