import json
import os
import re
import smtplib
from email.mime.text import MIMEText
from pathlib import Path

from playwright.sync_api import sync_playwright

SEARCHES_FILE = "searches.json"
SEEN_FILE = "seen_parts.json"

EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASS = os.environ.get("EMAIL_PASS")

PRICE_DROP_ALERT_THRESHOLD = 0.10  # 10%


def load_searches():
    path = Path(SEARCHES_FILE)
    if not path.exists():
        raise FileNotFoundError(f"{SEARCHES_FILE} not found")

    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"{SEARCHES_FILE} is empty")

    data = json.loads(text)
    searches = data.get("searches", [])

    if not searches:
        raise ValueError("No searches found in searches.json")

    return searches


def load_seen():
    path = Path(SEEN_FILE)
    if not path.exists():
        return {}

    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}

    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_seen(data):
    Path(SEEN_FILE).write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def extract_price(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    for line in lines:
        if "SEK" in line:
            if line == "SWE / SE / SEK /":
                continue

            m = re.search(r"([\d\s.,]+)\s*SEK", line)

            if m:
                raw = m.group(1)
                normalized = raw.replace(" ", "").replace(",", "")

                try:
                    return float(normalized)
                except Exception:
                    pass

    return None


def format_price(price):
    if price is None:
        return "hind puudub"

    return f"{price:.2f} SEK"


def is_price_allowed(price, max_price):
    if max_price is None:
        return True

    if price is None:
        return True

    return price <= max_price


def is_significant_price_drop(old_price, new_price, threshold=PRICE_DROP_ALERT_THRESHOLD):
    if old_price is None or new_price is None:
        return False

    if old_price <= 0:
        return False

    if new_price >= old_price:
        return False

    drop_pct = (old_price - new_price) / old_price
    return drop_pct >= threshold


def price_drop_percent(old_price, new_price):
    if old_price is None or new_price is None or old_price <= 0:
        return 0.0

    return ((old_price - new_price) / old_price) * 100


def send_email(search_name, new_items, cheaper_items, price_added_items):
    if not EMAIL_USER or not EMAIL_PASS:
        print("Email secrets missing")
        return

    if not new_items and not cheaper_items and not price_added_items:
        print("No email sent, no changes")
        return

    lines = []
    lines.append(f"Otsing: {search_name}")
    lines.append("")

    if new_items:
        lines.append("UUED KUULUTUSED")
        lines.append("")

        for item_search_name, title, price, url in new_items:
            lines.append(f"[{item_search_name}] {title}")
            lines.append(f"Hind: {format_price(price)}")
            lines.append(url)
            lines.append("")

    if cheaper_items:
        lines.append("HINNALANGUSED")
        lines.append("")

        for item in cheaper_items:
            item_search_name, title, old_price, new_price, drop_pct, url = item
            lines.append(f"[{item_search_name}] {title}")
            lines.append(f"Vana hind: {format_price(old_price)}")
            lines.append(f"Uus hind: {format_price(new_price)}")
            lines.append(f"Langus: -{drop_pct:.1f}%")
            lines.append(url)
            lines.append("")

    if price_added_items:
        lines.append("HIND LISATI HILJEM")
        lines.append("")

        for item_search_name, title, new_price, url in price_added_items:
            lines.append(f"[{item_search_name}] {title}")
            lines.append(f"Hind: {format_price(new_price)}")
            lines.append(url)
            lines.append("")

    body = "\n".join(lines)

    msg = MIMEText(body, _charset="utf-8")
    msg["Subject"] = (
        f"engine-watcher: "
        f"{len(new_items)} new, "
        f"{len(cheaper_items)} cheaper, "
        f"{len(price_added_items)} price added"
    )
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_USER

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)

    print("Email sent")


def main():
    print("Running TEST_PRICE_DROP logic...")

    old_price = 50000
    new_price_small = 47000
    new_price_big = 44000

    print("TEST small drop should be False:", is_significant_price_drop(old_price, new_price_small))
    print("TEST big drop should be True:", is_significant_price_drop(old_price, new_price_big))
    print("TEST big drop %:", price_drop_percent(old_price, new_price_big))


if __name__ == "__main__":
    main()
