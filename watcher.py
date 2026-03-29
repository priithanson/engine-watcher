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

MAX_RESULTS = 50  # 🚀 LIMIT SPEED FIX


def load_searches():
    return json.loads(Path(SEARCHES_FILE).read_text())["searches"]


def load_seen():
    path = Path(SEEN_FILE)
    if not path.exists():
        return {}
    return json.loads(path.read_text() or "{}")


def save_seen(data):
    Path(SEEN_FILE).write_text(json.dumps(data, indent=2))


def extract_price(text):
    m = re.search(r"([\d\s.,]+)\s*SEK", text)
    if not m:
        return None
    try:
        return float(m.group(1).replace(" ", "").replace(",", ""))
    except:
        return None


def format_price(p):
    return "hind puudub" if p is None else f"{p:.0f} SEK"


def is_significant_price_drop(old_price, new_price):
    if not old_price or not new_price:
        return False
    if new_price >= old_price:
        return False
    return (old_price - new_price) / old_price >= PRICE_DROP_ALERT_THRESHOLD


def price_drop_percent(old_price, new_price):
    return ((old_price - new_price) / old_price) * 100


def send_email(name, new, cheaper, added):
    if not (new or cheaper or added):
        print("No email sent, no changes")
        return

    body = []

    for s, t, p, u in new:
        body.append(f"[{s}] {t}\n{format_price(p)}\n{u}\n")

    for s, t, op, np, dp, u in cheaper:
        body.append(f"[{s}] {t}\n{format_price(op)} → {format_price(np)} (-{dp:.1f}%)\n{u}\n")

    for s, t, p, u in added:
        body.append(f"[{s}] {t}\n{format_price(p)}\n{u}\n")

    msg = MIMEText("\n".join(body))
    msg["Subject"] = f"{len(new)} new, {len(cheaper)} cheaper, {len(added)} added"
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_USER

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(EMAIL_USER, EMAIL_PASS)
        s.send_message(msg)

    print("Email sent")


def main():
    searches = load_searches()

    all_new, all_cheaper, all_added = [], [], []
    old_seen = load_seen()
    current_seen = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for search in searches:
            name = search["name"]
            url = search["url"]

            print("Running:", name)

            old_data = old_seen.get(name, {})
            current = {}

            page = browser.new_page()
            page.goto(url)
            page.wait_for_timeout(5000)

            links = page.locator("a")
            results = []
            seen = set()

            for i in range(min(links.count(), 200)):
                href = links.nth(i).get_attribute("href") or ""

                if "/ID-" in href and "/Motor/Motor-Diesel/" in href:
                    full = "https://www.bildelsbasen.se" + href
                    if full not in seen:
                        seen.add(full)
                        results.append(full)

                if len(results) >= MAX_RESULTS:
                    break

            print(name, "links:", len(results))

            detail = browser.new_page()

            for u in results:
                try:
                    detail.goto(u)
                    detail.wait_for_timeout(1500)
                    text = detail.locator("body").inner_text()
                    price = extract_price(text)
                    current[u] = {"price": price}
                except:
                    current[u] = {"price": None}

            detail.close()
            page.close()

            merged = dict(old_data)

            for u, item in current.items():
                old = old_data.get(u)
                np = item["price"]

                if not old:
                    all_new.append((name, u, np, u))
                else:
                    op = old.get("price")

                    if op is None and np:
                        all_added.append((name, u, np, u))

                    elif op and np and np < op:
                        if is_significant_price_drop(op, np):
                            all_cheaper.append((name, u, op, np, price_drop_percent(op, np), u))

                merged[u] = item

            current_seen[name] = merged

        browser.close()

    print("New:", len(all_new))
    print("Cheaper:", len(all_cheaper))
    print("Added:", len(all_added))

    send_email("MULTI", all_new, all_cheaper, all_added)
    save_seen(current_seen)


if __name__ == "__main__":
    main()
