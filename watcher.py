import json
import os
import re
import smtplib
from email.mime.text import MIMEText
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "https://www.bildelsbasen.se/sv-se/pb/S%C3%B6k/Bildelar/s6/Motor/Motor-Diesel/Alla?query=R9M&limit=100&sort_column=part_price_sort_sek&sort_direction=asc"
SEEN_FILE = "seen_parts.json"

EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASS = os.environ.get("EMAIL_PASS")


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
    except json.JSONDecodeError:
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
                except ValueError:
                    pass
    return None


def format_price(price):
    if price is None:
        return "hind puudub"
    return f"{price:.2f} SEK"


def send_email(new_items, cheaper_items, price_added_items):
    if not EMAIL_USER or not EMAIL_PASS:
        print("Email secrets missing")
        return

    if not new_items and not cheaper_items and not price_added_items:
        print("No email sent, no changes")
        return

    lines = []

    if new_items:
        lines.append("UUED KUULUTUSED")
        lines.append("")
        for title, price, url in new_items:
            lines.append(title)
            lines.append(f"Hind: {format_price(price)}")
            lines.append(url)
            lines.append("")

    if cheaper_items:
        lines.append("HINNALANGUSED")
        lines.append("")
        for title, old_price, new_price, url in cheaper_items:
            lines.append(title)
            lines.append(f"Vana hind: {format_price(old_price)}")
            lines.append(f"Uus hind: {format_price(new_price)}")
            lines.append(url)
            lines.append("")

    if price_added_items:
        lines.append("HIND LISATI HILJEM")
        lines.append("")
        for title, new_price, url in price_added_items:
            lines.append(title)
            lines.append(f"Hind: {format_price(new_price)}")
            lines.append(url)
            lines.append("")

    body = "\n".join(lines)

    msg = MIMEText(body, _charset="utf-8")
    msg["Subject"] = "Bildelsbasen R9M muutused"
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_USER

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)

    print("Email sent")


def main():
    print("Opening Bildelsbasen in browser...")

    old_seen = load_seen()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        search_page = browser.new_page()
        search_page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        search_page.wait_for_timeout(8000)

        links = search_page.locator("a")
        count = links.count()

        results = []
        seen_urls = set()

        for i in range(count):
            text = links.nth(i).inner_text().strip()
            href = links.nth(i).get_attribute("href") or ""

            is_product = (
                text.startswith("W")
                and "Motor Diesel" in text
                and "/Motor/Motor-Diesel/_/ID-" in href
            )

            if is_product:
                full_url = "https://www.bildelsbasen.se" + href

                if full_url not in seen_urls:
                    seen_urls.add(full_url)
                    results.append((text, full_url))

        print("Found engines:", len(results))

        detail_page = browser.new_page()
        current_data = {}

        for idx, (title, url) in enumerate(results, start=1):
            print(f"Checking detail {idx}/{len(results)}")

            try:
                detail_page.goto(url, wait_until="domcontentloaded", timeout=60000)
                detail_page.wait_for_timeout(2500)

                body_text = detail_page.locator("body").inner_text()
                price = extract_price(body_text)

                current_data[url] = {
                    "title": title,
                    "price": price
                }

            except Exception as e:
                print("Detail page failed:", url)
                print(str(e))
                current_data[url] = {
                    "title": title,
                    "price": None
                }

        detail_page.close()
        search_page.close()
        browser.close()

    new_items = []
    cheaper_items = []
    price_added_items = []

    for url, item in current_data.items():
        old_item = old_seen.get(url)
        new_price = item.get("price")

        if old_item is None:
            new_items.append((item["title"], new_price, url))
            continue

        old_price = old_item.get("price")

        if old_price is None and new_price is not None:
            price_added_items.append((item["title"], new_price, url))
        elif old_price is not None and new_price is not None and new_price < old_price:
            cheaper_items.append((item["title"], old_price, new_price, url))

    print("New engines:", len(new_items))
    print("Cheaper engines:", len(cheaper_items))
    print("Price added later:", len(price_added_items))

    send_email(new_items, cheaper_items, price_added_items)
    save_seen(current_data)


if __name__ == "__main__":
    main()
