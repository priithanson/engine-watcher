import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "https://www.bildelsbasen.se/sv-se/pb/S%C3%B6k/Bildelar/s6/Motor/Motor-Diesel/Alla?query=R9M&limit=100&sort_column=part_price_sort_sek&sort_direction=asc"
SEEN_FILE = "seen_parts.json"


def load_seen():
    path = Path(SEEN_FILE)
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    data = json.loads(text)
    if isinstance(data, list):
        return {}
    return data


def save_seen(items):
    Path(SEEN_FILE).write_text(
        json.dumps(items, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def extract_price(block_text):
    lines = [line.strip() for line in block_text.splitlines() if line.strip()]

    for line in lines:
        if "SEK" in line:
            match = re.search(r"([\d\s.,]+)\s*SEK", line)
            if match:
                raw = match.group(1)
                normalized = raw.replace(" ", "").replace(",", "")
                try:
                    return float(normalized)
                except ValueError:
                    pass

    return None


def main():
    print("Opening Bildelsbasen in browser...")

    old_seen = load_seen()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(8000)

        links = page.locator("a")
        count = links.count()

        results = {}
        seen_in_page = set()

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

                if full_url in seen_in_page:
                    continue

                seen_in_page.add(full_url)

                container_text = links.nth(i).locator("xpath=ancestor::*[self::div or self::article][1]").inner_text()
                price = extract_price(container_text)

                results[full_url] = {
                    "title": text,
                    "price": price
                }

        browser.close()

    new_items = []
    cheaper_items = []

    for url, item in results.items():
        if url not in old_seen:
            new_items.append((item["title"], item["price"], url))
        else:
            old_price = old_seen[url].get("price")
            new_price = item.get("price")

            if old_price is not None and new_price is not None and new_price < old_price:
                cheaper_items.append((item["title"], old_price, new_price, url))

    print("Found engines total:", len(results))
    print("New engines:", len(new_items))
    print("Cheaper engines:", len(cheaper_items))

    if new_items:
        print("=== NEW ITEMS ===")
        for title, price, url in new_items[:10]:
            print(title)
            print("Price:", price)
            print(url)
            print("-----")

    if cheaper_items:
        print("=== PRICE DROPS ===")
        for title, old_price, new_price, url in cheaper_items[:10]:
            print(title)
            print("Old price:", old_price)
            print("New price:", new_price)
            print(url)
            print("-----")

    save_seen(results)


if __name__ == "__main__":
    main()
