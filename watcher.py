import json
import time
import re
import os
import smtplib
from email.mime.text import MIMEText

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options


SEARCHES_FILE = "searches.json"
SEEN_FILE = "seen_parts.json"

EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASS = os.environ.get("EMAIL_PASS")

MAX_RESULTS = 100
PRICE_DROP_ALERT_THRESHOLD = 0.10  # 10%


def load_searches():
    with open(SEARCHES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    searches = data.get("searches", [])
    if not isinstance(searches, list):
        raise ValueError("searches.json must contain a 'searches' list")

    return searches


def load_seen():
    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_seen(data):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


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
            s = s.replace(",", "")
        else:
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

    matches = re.finditer(r"([\d][\d\s.,\xa0]*)\s*SEK\b", text, flags=re.MULTILINE)
    for match in matches:
        price = parse_price_string(match.group(1))
        if price is not None:
            return price

    return None


def format_price(price):
    if price is None:
        return "hind puudub"
    return f"{price:.2f} SEK"


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


def get_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1400,2000")
    return webdriver.Chrome(options=options)


def run():
    searches = load_searches()
    seen = load_seen()

    print(f"Loaded searches: {len(searches)}")
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

    new_items = []
    cheaper_items = []
    price_added_items = []

    driver = get_driver()

    for search in searches:
        name = search["name"]
        site = search["site"]
        url = search["url"]
        max_price = search.get("max_price")

        if site.lower() != "bildelsbasen":
            print("Skipping unsupported site:", site)
            continue

        print(f"Running search: {name}")
        print(f"URL: {url}")
        print(f"Max price: {max_price}")

        if name not in seen or not isinstance(seen[name], dict):
            seen[name] = {}

        old_search_seen = seen[name]

        driver.get(url)
        time.sleep(4)

        link_elements = driver.find_elements(By.CSS_SELECTOR, "a[href*='/ID-']")
        results = []
        seen_urls = set()

        for el in link_elements:
            href = el.get_attribute("href") or ""
            text = (el.text or "").strip()

            is_product = (
                "Motor-Diesel" in href
                and "/ID-" in href
                and href not in seen_urls
            )

            if is_product:
                seen_urls.add(href)
                results.append((text, href))

            if len(results) >= MAX_RESULTS:
                break

        print(f"[{name}] Found engines: {len(results)}")

        current_search_data = {}

        for idx, (title, detail_url) in enumerate(results, start=1):
            print(f"[{name}] Checking detail {idx}/{len(results)}")

            try:
                driver.get(detail_url)
                time.sleep(2)

                body_text = driver.find_element(By.TAG_NAME, "body").text
                price = extract_price(body_text)

                if not is_price_allowed(price, max_price):
                    print(f"[{name}] Skipping over max_price:", price, detail_url)
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

        merged_search_data = dict(old_search_seen)

        for detail_url, item in current_search_data.items():
            old_item = old_search_seen.get(detail_url)
            new_price = item.get("price")

            if old_item is None:
                if new_price is not None:
                    new_items.append((name, item["title"], new_price, detail_url))
            else:
                old_price = old_item.get("price")

                if old_price is None and new_price is not None:
                    price_added_items.append((name, item["title"], new_price, detail_url))

                elif old_price is not None and new_price is not None and new_price < old_price:
                    if is_significant_price_drop(old_price, new_price):
                        drop_pct = price_drop_percent(old_price, new_price)
                        cheaper_items.append(
                            (name, item["title"], old_price, new_price, drop_pct, detail_url)
                        )

            if old_item is not None and new_price is None and old_item.get("price") is not None:
                merged_search_data[detail_url] = {
                    "title": item.get("title") or old_item.get("title"),
                    "price": old_item.get("price")
                }
            else:
                merged_search_data[detail_url] = {
                    "title": item.get("title"),
                    "price": new_price
                }

        seen[name] = merged_search_data

    driver.quit()

    save_seen(seen)

    print(f"New engines: {len(new_items)}")
    print(f"Cheaper engines: {len(cheaper_items)}")
    print(f"Price added later: {len(price_added_items)}")

    send_email("MULTI", new_items, cheaper_items, price_added_items)


if __name__ == "__main__":
    run()
