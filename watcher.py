import re
from playwright.sync_api import sync_playwright

URL = "https://www.bildelsbasen.se/sv-se/pb/S%C3%B6k/Bildelar/s6/Motor/Motor-Diesel/Alla?query=R9M&limit=100&sort_column=part_price_sort_sek&sort_direction=asc"


def extract_price(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    for line in lines:
        if "SEK" in line:
            m = re.search(r"([\d\s.,]+)\s*SEK", line)
            if m:
                raw = m.group(1)
                normalized = raw.replace(" ", "").replace(",", "")
                try:
                    return float(normalized)
                except ValueError:
                    pass
    return None


def main():
    print("Opening Bildelsbasen in browser...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(8000)

        links = page.locator("a")
        count = links.count()

        results = []
        seen = set()

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

                if full_url not in seen:
                    seen.add(full_url)
                    results.append((text, full_url))

        print("Found engines:", len(results))
        print("Checking first 5 detail pages for price...")

        detail_page = browser.new_page()

        for title, url in results[:5]:
            detail_page.goto(url, wait_until="domcontentloaded", timeout=60000)
            detail_page.wait_for_timeout(3000)

            body_text = detail_page.locator("body").inner_text()
            price = extract_price(body_text)

            print(title)
            print("Price:", price)
            print(url)
            print("-----")

        detail_page.close()
        browser.close()


if __name__ == "__main__":
    main()
