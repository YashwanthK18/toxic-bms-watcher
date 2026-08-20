#!/usr/bin/env python3

import json
import os
import re
import sys
import time
import urllib.parse
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = Path(os.environ.get("CONFIG_PATH", ROOT / "config.json"))
STATE_PATH = Path(os.environ.get("STATE_PATH", ROOT / "state.json"))


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-IN,en-US;q=0.9,en;q=0.8",
    "Upgrade-Insecure-Requests": "1",
    "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
}


THEATRES = {
    "URBL": "Urvashi Cinema",
    "VCCB": "Victory Cinema",
    "PVOO": "PVR Orion Mall",
}


def load_json(path, default=None):
    if not path.exists():
        return default

    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)


def load_config():
    cfg = load_json(CONFIG_PATH, default={}) or {}

    env_map = {
        "TARGET_URL": "target_url",
        "THEATRE": "theatre",
        "MOVIE": "movie",
        "REQUESTED_DATE": "requested_date",
        "TELEGRAM_BOT_TOKEN": "telegram_bot_token",
        "TELEGRAM_CHAT_ID": "telegram_chat_id",
    }

    for env_key, cfg_key in env_map.items():
        if os.environ.get(env_key):
            cfg[cfg_key] = os.environ[env_key]

    if os.environ.get("HEADERS_JSON"):
        cfg["headers"] = json.loads(os.environ["HEADERS_JSON"])

    if cfg.get("url_template") and cfg.get("requested_date"):
        cfg["target_url"] = cfg["url_template"].format(
            date=cfg["requested_date"]
        )

    required = [
        "target_url",
        "telegram_bot_token",
        "telegram_chat_id",
    ]

    detector = cfg.get("detector")

    if detector in ("bms_date", "venue_date"):
        required.append("requested_date")
    elif detector != "venue_date":
        required.append("theatre")

    if detector == "venue_date" and not (
        cfg.get("venue_code") or cfg.get("venue_codes")
    ):
        sys.exit(
            "venue_date detector needs 'venue_code' or 'venue_codes'"
        )

    missing = [k for k in required if not cfg.get(k)]

    if missing:
        sys.exit(
            f"Missing required config: {', '.join(missing)}"
        )

    return cfg


def send_telegram(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    response = requests.post(
        url,
        json={
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": False,
        },
        timeout=30,
    )

    response.raise_for_status()


def fetch(cfg):
    headers = dict(DEFAULT_HEADERS)
    headers.update(cfg.get("headers", {}))

    scraper_key = os.environ.get("SCRAPERAPI_KEY")

    if scraper_key:
        api_url = "https://api.scraperapi.com/?" + urllib.parse.urlencode(
            {
                "api_key": scraper_key,
                "country_code": "in",
                "url": cfg["target_url"],
            }
        )

        response = requests.get(
            api_url,
            timeout=90,
        )

        response.raise_for_status()

        return response.text

    proxy = os.environ.get("PROXY_URL")

    proxies = (
        {"http": proxy, "https": proxy}
        if proxy
        else None
    )

    session = requests.Session()
    session.headers.update(headers)

    try:
        session.get(
            "https://in.bookmyshow.com/",
            timeout=30,
            proxies=proxies,
        )
    except requests.RequestException:
        pass

    response = session.get(
        cfg["target_url"],
        timeout=30,
        proxies=proxies,
        headers={
            "Referer":
                "https://in.bookmyshow.com/explore/movies-bengaluru"
        },
    )

    response.raise_for_status()

    return response.text


def get_open_venues(page_text, cfg):
    """
    Check each target theatre independently.

    BMS exposes a booking URL containing:
        /<venue_code>/<date>

    when that theatre is bookable for that exact date.
    """

    date = cfg["requested_date"]

    codes = cfg.get("venue_codes")

    if not codes:
        codes = [cfg["venue_code"]]

    open_venues = []

    for code in codes:
        pattern = f"/{code}/{date}"

        if pattern.lower() in page_text.lower():
            open_venues.append(code)

    return open_venues


def is_available_venue_date(page_text, cfg):
    return bool(
        get_open_venues(page_text, cfg)
    )


def is_available_bms_date(page_text, cfg):
    requested = cfg["requested_date"]

    floor = cfg.get(
        "min_references",
        10,
    )

    tokens = re.findall(
        r"20\d{6}",
        page_text,
    )

    if not tokens:
        return False

    counts = Counter(tokens)

    top_date, _ = counts.most_common(1)[0]

    requested_count = counts.get(
        requested,
        0,
    )

    return (
        top_date == requested
        and requested_count >= floor
    )


def is_available_generic(page_text, cfg):
    haystack = re.sub(
        r"\s+",
        " ",
        page_text,
    ).lower()

    theatre = re.sub(
        r"\s+",
        " ",
        cfg["theatre"],
    ).lower().strip()

    if theatre not in haystack:
        return False

    movie = cfg.get("movie")

    if movie:
        movie_normalized = re.sub(
            r"\s+",
            " ",
            movie,
        ).lower().strip()

        if movie_normalized not in haystack:
            return False

    open_signals = cfg.get(
        "open_signals",
        [
            "book tickets",
            "book now",
            '"showtimes"',
            "showtime",
            "select seats",
        ],
    )

    closed_signals = cfg.get(
        "closed_signals",
        [
            "notify me",
            "coming soon",
        ],
    )

    has_open = any(
        signal.lower() in haystack
        for signal in open_signals
    )

    only_closed = (
        any(
            signal.lower() in haystack
            for signal in closed_signals
        )
        and not has_open
    )

    return has_open and not only_closed


def is_available(page_text, cfg):
    detector = cfg.get("detector")

    if detector == "venue_date":
        return is_available_venue_date(
            page_text,
            cfg,
        )

    if detector == "bms_date":
        return is_available_bms_date(
            page_text,
            cfg,
        )

    return is_available_generic(
        page_text,
        cfg,
    )


def send_status_update(
    cfg,
    open_venues,
    checked_at,
):
    requested_date = cfg["requested_date"]

    pretty_date = (
        f"{requested_date[6:8]}-"
        f"{requested_date[4:6]}-"
        f"{requested_date[0:4]}"
    )

    lines = [
        "🔎 Toxic BMS Status",
        "",
        "🎬 Toxic: A Fairy Tale for Grown-ups",
        f"📅 {pretty_date}",
        "",
    ]

    for code, name in THEATRES.items():

        if code in open_venues:
            status = "🚨 BOOKING OPEN"
        else:
            status = "❌ Not released"

        lines.append(
            f"{status} — {name}"
        )

    lines.extend(
        [
            "",
            f"🕐 Checked: {checked_at}",
            "🔄 Next check: ~5 minute",
        ]
    )

    send_telegram(
        cfg["telegram_bot_token"],
        cfg["telegram_chat_id"],
        "\n".join(lines),
    )


def send_booking_alert(
    cfg,
    open_venues,
):
    requested_date = cfg["requested_date"]

    pretty_date = (
        f"{requested_date[6:8]}-"
        f"{requested_date[4:6]}-"
        f"{requested_date[0:4]}"
    )

    venue_names = [
        THEATRES.get(
            code,
            code,
        )
        for code in open_venues
    ]

    message = (
        "🚨 TOXIC BOOKINGS OPEN!\n\n"
        "🎬 Toxic: A Fairy Tale for Grown-ups\n"
        f"📅 {pretty_date}\n\n"
        "✅ Booking available at:\n"
        + "\n".join(
            f"• {name}"
            for name in venue_names
        )
        + "\n\n"
        f"🎟️ Book now:\n{cfg['target_url']}"
    )

    send_telegram(
        cfg["telegram_bot_token"],
        cfg["telegram_chat_id"],
        message,
    )


def main():

    cfg = load_config()

    state = load_json(
        STATE_PATH,
        default={
            "available": False,
        },
    ) or {
        "available": False,
    }

    target_desc = (
        cfg.get("theatre")
        or cfg.get(
            "requested_date",
            "target",
        )
    )

    label = (
        f"{cfg.get('movie', 'movie')}"
        f" @ {target_desc}"
    )

    try:
        page = fetch(cfg)

    except requests.RequestException as exc:

        print(
            f"[{label}] fetch failed: {exc}"
        )

        return 0

    open_venues = []

    if cfg.get("detector") == "venue_date":

        open_venues = get_open_venues(
            page,
            cfg,
        )

        available = bool(
            open_venues
        )

    else:

        available = is_available(
            page,
            cfg,
        )

    previous_available = state.get(
        "available",
        False,
    )

    print(
        f"[{label}] "
        f"available={available} "
        f"(was {previous_available})"
    )

    if open_venues:
        print(
            "Open venues:",
            ", ".join(open_venues),
        )

    # -------------------------------------------------
    # IMMEDIATE BOOKING ALERT
    # -------------------------------------------------

    if available and not previous_available:

        if cfg.get("detector") == "venue_date":

            send_booking_alert(
                cfg,
                open_venues,
            )

        else:

            requested_date = cfg["requested_date"]

            pretty_date = (
                f"{requested_date[6:8]}-"
                f"{requested_date[4:6]}-"
                f"{requested_date[0:4]}"
            )

            message = (
                "🚨 TOXIC BOOKINGS OPEN!\n\n"
                f"🎬 {cfg.get('movie', 'Movie')}\n"
                f"📅 {pretty_date}\n\n"
                f"🎟️ Book now:\n"
                f"{cfg['target_url']}"
            )

            send_telegram(
                cfg["telegram_bot_token"],
                cfg["telegram_chat_id"],
                message,
            )

        print(
            f"[{label}] notification sent"
        )

    # -------------------------------------------------
    # 10-MINUTE HEARTBEAT
    # -------------------------------------------------

    now = datetime.now(ZoneInfo("Asia/Kolkata"))

    if now.minute % 5 == 0 or os.environ.get("MANUAL_TEST") == "true":

        checked_at = now.strftime(
            "%I:%M %p"
        )

        send_status_update(
            cfg,
            open_venues,
            checked_at,
        )

        print(
            f"[{label}] "
            "10-minute status sent"
        )

    # -------------------------------------------------
    # SAVE CURRENT AVAILABILITY
    # -------------------------------------------------

    if available != previous_available:

        state["available"] = available

        state["checked_at"] = int(
            time.time()
        )

        save_json(
            STATE_PATH,
            state,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
