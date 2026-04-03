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
    except:
        return {}


def save_seen(data):
    Path(SEEN_FILE).write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def extract_price(text):
    if not text:
        return None

    m = re.search(r"([\d\s.,]+)\s*SEK", text)
    if not m:
        return None

    raw = m.group(1)
    normalized = raw.replace(" ", "").replace(",", "")

    try:
        return float(normalized)
    except:
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

    for item_search_name, title, price, url in new_items:
        lines.append(f"[{item_search_name}] {title}")
        lines.append(f"Hind: {format_price(price)}")
        lines.append(url)
        lines.append("")

    body = "\n".join(lines)

    msg = MIMEText(body, _charset="utf-8")
    msg["Subject"] = f"engine-watcher: {len(new_items)} new"
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_USER

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)

    print("Email sent")


def main():
    searches = load_searches()
    old_seen = load_seen()
    current_seen = {}

    all_new = []

    print("Opening browser...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for search in searches:
            search_name = search["name"]
            search_url = search["url"]
            max_price = search.get("max_price")

            print("\n======================")
            print("Running search:", search_name)

            old_search_seen = old_seen.get(search_name, {})
            current_search_data = {}

            page = browser.new_page()
            page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(8000)

            links = page.locator("a")
            count = links.count()

            results = []
            seen_urls = set()

            for i in range(count):
                text = links.nth(i).inner_text().strip()
                href = links.nth(i).get_attribute("href") or ""

                # 🔥 DEBUG
                if "/ID-" in href:
                    print(f"[{search_name}] LINK DEBUG:", text[:120], "|", href)

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

            print(f"[{search_name}] Found engines:", len(results))

            detail_page = browser.new_page()

            for title, detail_url in results:
                try:
                    detail_page.goto(detail_url)
                    detail_page.wait_for_timeout(2000)

                    body = detail_page.locator("body").inner_text()
                    price = extract_price(body)

                    if not is_price_allowed(price, max_price):
                        continue

                    current_search_data[detail_url] = {
                        "title": title,
                        "price": price
                    }

                except Exception as e:
                    print("Detail failed:", detail_url)
                    print(e)

            detail_page.close()
            page.close()

            for url, item in current_search_data.items():
                if url not in old_search_seen:
                    all_new.append((search_name, item["title"], item["price"], url))

            current_seen[search_name] = current_search_data

        browser.close()

    print("\nNew engines:", len(all_new))
    send_email("MULTI", all_new, [], [])
    save_seen(current_seen)


if __name__ == "__main__":
    main()
