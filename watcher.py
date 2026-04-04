 import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

SEARCHES_FILE = "searches.json"

DEBUG_SEARCH_NAME = "R9M"
DEBUG_PRICE_URL_PART = "ID-67329606"


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
    except Exception:
        return None


def main():
    searches = load_searches()

    debug_search = None
    for search in searches:
        if search["name"] == DEBUG_SEARCH_NAME:
            debug_search = search
            break

    if debug_search is None:
        raise ValueError(f"Search '{DEBUG_SEARCH_NAME}' not found in searches.json")

    search_name = debug_search["name"]
    search_url = debug_search["url"]

    print("DEBUG MODE")
    print("Search:", search_name)
    print("URL:", search_url)
    print("Looking for detail URL containing:", DEBUG_PRICE_URL_PART)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        page = browser.new_page()
        page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(5000)

        links = page.locator("a")
        count = links.count()

        target_url = None

        for i in range(count):
            href = links.nth(i).get_attribute("href") or ""
            full_url = "https://www.bildelsbasen.se" + href if href.startswith("/") else href

            if DEBUG_PRICE_URL_PART in full_url:
                target_url = full_url
                print("FOUND TARGET URL ON SEARCH PAGE:")
                print(target_url)
                break

        page.close()

        if not target_url:
            print("TARGET URL NOT FOUND ON SEARCH PAGE")
            browser.close()
            return

        detail_page = browser.new_page()
        detail_page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
        detail_page.wait_for_timeout(3000)

        body_text = detail_page.locator("body").inner_text()
        price = extract_price(body_text)

        print("\n================ DEBUG PRICE PAGE ================")
        print("DEBUG URL:", target_url)
        print("DEBUG EXTRACTED PRICE:", price)
        print("\nDEBUG BODY START:")
        print(body_text[:4000])

        print("\nDEBUG SEK LINES:")
        found_any = False
        for line in body_text.splitlines():
            if "SEK" in line:
                found_any = True
                print("SEK LINE:", line.strip())

        if not found_any:
            print("No SEK lines found in body text")

        print("================ END DEBUG PRICE PAGE ================\n")

        detail_page.close()
        browser.close()


if __name__ == "__main__":
    main()
