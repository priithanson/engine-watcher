from playwright.sync_api import sync_playwright

URL = "https://www.bildelsbasen.se/sv-se/pb/S%C3%B6k/Bildelar/s6/Motor/Motor-Diesel/Alla?query=R9M&limit=100&sort_column=part_price_sort_sek&sort_direction=asc"

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

        for title, url in results[:10]:
            print(title)
            print(url)
            print("-----")

        browser.close()

if __name__ == "__main__":
    main()
