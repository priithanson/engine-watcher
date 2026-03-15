from playwright.sync_api import sync_playwright

print("VERSION 2")

URL = "https://www.bildelsbasen.se/sv-se/pb/S%C3%B6k/Bildelar/s6/Motor/Motor-Diesel/Alla?query=R9M&limit=100&sort_column=part_price_sort_sek&sort_direction=asc"

def main():
    print("Opening Bildelsbasen in browser...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        page = browser.new_page()

        page.goto(URL, wait_until="networkidle", timeout=60000)

        page.wait_for_timeout(5000)

        links = page.locator("a[href*='/part/']")
        count = links.count()

        print("Found engines:", count)

        for i in range(min(count, 10)):
            title = links.nth(i).inner_text().strip()
            href = links.nth(i).get_attribute("href")

            if href and title:
                print(title)
                print("https://www.bildelsbasen.se" + href)
                print("-----")

        browser.close()

if __name__ == "__main__":
    main()
