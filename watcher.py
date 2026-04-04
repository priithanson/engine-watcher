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


def parse_price_string(raw):
    if raw is None:
        return None

    s = raw.replace("\xa0", " ").strip()
    s = re.sub(r"[^\d,.\s]", "", s)
    s = re.sub(r"\s+", "", s)

    if not s:
        return None

    if "," in s and "." in s:
        if s.rfind(".") > s.rfind(","):
            # 23,000.00 -> 23000.00
            s = s.replace(",", "")
        else:
            # 23.000,00 -> 23000.00
            s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        if len(s.split(",")[-1]) == 2:
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "." in s:
        if len(s.split(".")[-1]) != 2:
            s = s.replace(".", "")

    try:
        return float(s)
    except Exception:
        return None


def extract_price(text):
    if not text:
        return None

    lines = [line.strip() for line in text.splitlines() if line.strip()]

    skip_keywords = (
        "frakt",
        "postnord",
        "dsv",
        "pallet",
        "hämta hos oss",
        "hämta",
        "onlineköp",
        "import",
        "tull",
        "avgift",
    )

    for line in lines:
        lower = line.lower()

        if line == "SWE / SE / SEK /":
            continue

        if "SEK" not in line:
            continue

        if any(keyword in lower for keyword in skip_keywords):
            continue

        m = re.search(r"([\d][\d\s.,\xa0]*)\s*SEK\b", line)
        if m:
            price = parse_price_string(m.group(1))
            if price is not None:
                return price

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

        for item_search_name, title, old_price, new_price, drop_pct, url in cheaper_items:
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
    searches = load_searches()

    print("Loaded searches:", len(searches))
    for s in searches:
        print(
            "-",
            s["name"],
            "|",
            s["site"],
            "|",
            s["url"],
            "| max_price:",
            s.get("max_price")
        )

    all_new = []
    all_cheaper = []
    all_price_added = []

    old_seen = load_seen()
    current_seen = {}

    print("Opening Bildelsbasen in browser...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for search in searches:
            search_name = search["name"]
            search_site = search["site"]
            search_url = search["url"]
            max_price = search.get("max_price")

            if search_site.lower() != "bildelsbasen":
                print("Skipping unsupported site:", search_site)
                continue

            print("Running search:", search_name)
            print("URL:", search_url)
            print("Max price:", max_price)

            old_search_seen = old_seen.get(search_name, {})
            current_search_data = {}

            search_page = browser.new_page()
            search_page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
            search_page.wait_for_timeout(8000)

            links = search_page.locator("a")
            count = links.count()

            results = []
            seen_urls = set()

            for i in range(count):
                text = links.nth(i).inner_text().strip()
                href = links.nth(i).get_attribute("href") or ""

                is_product = (
                    "Motor-Diesel" in href
                    and "/ID-" in href
                )

                if is_product:
                    full_url = "https://www.bildelsbasen.se" + href if href.startswith("/") else href

                    if full_url not in seen_urls:
                        seen_urls.add(full_url)
                        results.append((text, full_url))

            print(f"[{search_name}] Found engines:", len(results))

            detail_page = browser.new_page()

            for idx, (title, detail_url) in enumerate(results, start=1):
                print(f"[{search_name}] Checking detail {idx}/{len(results)}")

                try:
                    detail_page.goto(detail_url, wait_until="domcontentloaded", timeout=60000)
                    detail_page.wait_for_timeout(2500)

                    body_text = detail_page.locator("body").inner_text()
                    price = extract_price(body_text)

                    if not is_price_allowed(price, max_price):
                        print(f"[{search_name}] Skipping over max_price:", price, detail_url)
                        continue

                    current_search_data[detail_url] = {
                        "title": title if title else "Motor Diesel",
                        "price": price
                    }

                except Exception as e:
                    print("Detail page failed:", detail_url)
                    print(str(e))

                    current_search_data[detail_url] = {
                        "title": title if title else "Motor Diesel",
                        "price": None
                    }

            detail_page.close()
            search_page.close()

            merged_search_data = dict(old_search_seen)

            for url, item in current_search_data.items():
                old_item = old_search_seen.get(url)
                new_price = item.get("price")

                if old_item is None:
                    if new_price is not None:
                        all_new.append((search_name, item["title"], new_price, url))
                else:
                    old_price = old_item.get("price")

                    if old_price is None and new_price is not None:
                        all_price_added.append((search_name, item["title"], new_price, url))

                    elif old_price is not None and new_price is not None and new_price < old_price:
                        if is_significant_price_drop(old_price, new_price):
                            drop_pct = price_drop_percent(old_price, new_price)
                            all_cheaper.append(
                                (search_name, item["title"], old_price, new_price, drop_pct, url)
                            )

                if old_item is not None and new_price is None and old_item.get("price") is not None:
                    merged_search_data[url] = {
                        "title": item.get("title") or old_item.get("title"),
                        "price": old_item.get("price")
                    }
                else:
                    merged_search_data[url] = {
                        "title": item.get("title"),
                        "price": new_price
                    }

            current_seen[search_name] = merged_search_data

        browser.close()

    print("New engines:", len(all_new))
    print("Cheaper engines:", len(all_cheaper))
    print("Price added later:", len(all_price_added))

    send_email("MULTI", all_new, all_cheaper, all_price_added)
    save_seen(current_seen)


if __name__ == "__main__":
    main()
