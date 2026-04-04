import re
from playwright.sync_api import sync_playwright

DEBUG_URL = "https://www.bildelsbasen.se/sv-se/pb/S%C3%B6k/Bildelar/s1/Nissan/NISSAN-QASHQAI/2014_2017/Motor/Motor-Diesel/_/ID-67329606/1010201Q5B"


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
    print("DEBUG DIRECT URL")
    print("URL:", DEBUG_URL)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(DEBUG_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(4000)

        body = page.locator("body").inner_text()
        price = extract_price(body)

        print("\nPRICE:", price)
        print("\nSEK LINES:")
        found = False
        for line in body.splitlines():
            if "SEK" in line:
                found = True
                print(line.strip())

        if not found:
            print("No SEK lines found")

        browser.close()


if __name__ == "__main__":
    main()
