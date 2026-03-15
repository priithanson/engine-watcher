from playwright.sync_api import sync_playwright

URL = "https://www.bildelsbasen.se/sv-se/pb/S%C3%B6k/Bildelar/s6/Motor/Motor-Diesel/Alla?query=R9M&limit=100&sort_column=part_price_sort_sek&sort_direction=asc"

def main():
    print("Opening Bildelsbasen in browser...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(8000)

        print("PAGE TITLE:", page.title())
        print("FINAL URL:", page.url)

        body_text = page.locator("body").inner_text()
        print("BODY START:")
        print(body_text[:2000])
        print("BODY END")

        links = page.locator("a[href*='/part/']")
        count = links.count()
        print("Found engines:", count)

        browser.close()

if __name__ == "__main__":
    main()
