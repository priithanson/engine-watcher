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

        links = page.locator("a")
        count = links.count()
        print("TOTAL LINKS:", count)

        for i in range(min(count, 40)):
            text = links.nth(i).inner_text().strip()
            href = links.nth(i).get_attribute("href")
            print(f"LINK {i}:")
            print("TEXT:", text)
            print("HREF:", href)
            print("-----")

        browser.close()

if __name__ == "__main__":
    main()
