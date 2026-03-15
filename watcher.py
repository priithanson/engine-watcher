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

        search_page = browser.new_page()
        search_page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        search_page.wait_for_timeout(8000)

        links = search_page.locator("a")
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

        detail_page = browser.new_page()

        title, url = results[0]
        print("Testing first result:")
        print(title)
        print(url)

        detail_page.goto(url, wait_until="domcontentloaded", timeout=60000)
        detail_page.wait_for_timeout(5000)

        body_text = detail_page.locator("body").inner_text()
        price = extract_price(body_text)

        print("Detected price:", price)
        print("PRICE-RELATED LINES START")

        for line in body_text.splitlines():
            clean = line.strip()
            if clean and (
                "SEK" in clean
                or "Pris" in clean
                or "moms" in clean.lower()
                or "frakt" in clean.lower()
            ):
                print(clean)

        print("PRICE-RELATED LINES END")

        detail_page.close()
        search_page.close()
        browser.close()


if __name__ == "__main__":
    main()
