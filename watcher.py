import json
import re
from pathlib import Path
from playwright.sync_api import sync_playwright

SEARCHES_FILE = "searches.json"

DEBUG_SEARCH_NAME = "R9M"
DEBUG_PRICE_URL_PART = "ID-67329606"


def load_searches():
    path = Path(SEARCHES_FILE)
    text = path.read_text(encoding="utf-8").strip()
    data = json.loads(text)
    return data.get("searches", [])


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


def main():
    searches = load_searches()

    debug_search = None
    for s in searches:
        if s["name"] == DEBUG_SEARCH_NAME:
            debug_search = s
            break

    if not debug_search:
        print("Search not found")
        return

    search_url = debug_search["url"]

    print("DEBUG MODE")
    print("Search:", DEBUG_SEARCH_NAME)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        page = browser.new_page()
        page.goto(search_url)
        page.wait_for_timeout(5000)

        links = page.locator("a")
        count = links.count()

        target_url = None

        for i in range(count):
            href = links.nth(i).get_attribute("href") or ""
            full = "https://www.bildelsbasen.se" + href if href.startswith("/") else href

            if DEBUG_PRICE_URL_PART in full:
                target_url = full
                print("FOUND:", full)
                break

        if not target_url:
            print("NOT FOUND")
            browser.close()
            return

        detail = browser.new_page()
        detail.goto(target_url)
        detail.wait_for_timeout(3000)

        body = detail.locator("body").inner_text()
        price = extract_price(body)

        print("\n=== DEBUG ===")
        print("URL:", target_url)
        print("PRICE:", price)

        print("\nSEK LINES:")
        for line in body.splitlines():
            if "SEK" in line:
                print(line.strip())

        browser.close()


if __name__ == "__main__":
    main()
