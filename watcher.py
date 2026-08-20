import os
import time
import requests
from datetime import datetime

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

MOVIE_ID = "ET00378770"
DATE = "20260826"
CITY = "BANG"

THEATRES = {
    "URBL": "Urvashi Cinema",
    "VCCB": "Victory Cinema",
    "PVOO": "PVR Orion Mall",
}

CHECK_INTERVAL = 60

API_URL = "https://in.bookmyshow.com/pwa/api/de/showtimes/byevent"


def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    response = requests.post(
        url,
        json={
            "chat_id": CHAT_ID,
            "text": message,
            "disable_web_page_preview": True,
        },
        timeout=20,
    )

    response.raise_for_status()


def check_bms():
    params = {
        "regionCode": CITY,
        "subCode": "",
        "eventCode": MOVIE_ID,
        "dateCode": DATE,
    }

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/151.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
    }

    response = requests.get(
        API_URL,
        params=params,
        headers=headers,
        timeout=30,
    )

    print(
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        response.status_code,
        response.url,
    )

    response.raise_for_status()

    return response.json()


def find_target_theatres(data):
    """
    Look recursively through the BMS response and find
    our three cinema codes/names.
    """

    found = {}

    def walk(obj):
        if isinstance(obj, dict):

            text = " ".join(
                str(obj.get(key, ""))
                for key in (
                    "venueCode",
                    "venue_code",
                    "cinemaCode",
                    "cinema_code",
                    "code",
                    "name",
                    "venueName",
                    "venue_name",
                )
            ).lower()

            for code, name in THEATRES.items():
                if (
                    code.lower() in text
                    or name.lower() in text
                ):
                    found[code] = obj

            for value in obj.values():
                walk(value)

        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(data)

    return found


def main():
    print("🎬 Toxic BMS watcher started")
    print(f"Movie: {MOVIE_ID}")
    print(f"Date: {DATE}")
    print("Theatres:", ", ".join(THEATRES.values()))

    send_telegram(
        "🟢 Toxic BMS watcher started!\n\n"
        "Monitoring:\n"
        "• Urvashi Cinema\n"
        "• Victory Cinema\n"
        "• PVR Orion Mall\n\n"
        "Checking every 60 seconds."
    )

    notified = set()

    while True:
        try:
            data = check_bms()

            theatres = find_target_theatres(data)

            print(
                "Target theatres found:",
                list(theatres.keys())
            )

            for code, theatre_data in theatres.items():

                # Convert the theatre object to text so we can
                # detect whether showtimes have appeared.
                text = str(theatre_data).lower()

                # We only alert when the theatre object contains
                # meaningful show/showtime information.
                has_showtime = any(
                    key in text
                    for key in (
                        "showtime",
                        "show_time",
                        "session",
                        "showtimegroup",
                        "sessions",
                    )
                )

                if has_showtime and code not in notified:

                    theatre_name = THEATRES[code]

                    booking_url = (
                        f"https://in.bookmyshow.com/cinemas/"
                        f"BANG/{code}/buytickets/{code}/{DATE}"
                    )

                    message = (
                        "🚨 TOXIC BOOKINGS MAY BE OPEN!\n\n"
                        f"🎬 Toxic: A Fairy Tale for Grown-ups\n"
                        f"📅 26 August 2026\n"
                        f"📍 {theatre_name}\n\n"
                        f"🎟️ Book:\n{booking_url}"
                    )

                    send_telegram(message)

                    print(message)

                    notified.add(code)

        except Exception as e:
            print("ERROR:", repr(e))

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
