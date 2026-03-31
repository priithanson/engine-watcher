import json
import time
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options


MAX_RESULTS = 100  # 🚀 rohkem tulemusi


def load_json(file):
    try:
        with open(file, "r") as f:
            return json.load(f)
    except:
        return {}


def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2)


def extract_price(text):
    if not text:
        return None

    match = re.search(r"([\d\s,.]+)\s*SEK", text)
    if not match:
        return None

    price_str = match.group(1)
    price_str = price_str.replace(" ", "").replace(",", "")

    try:
        return float(price_str)
    except:
        return None


def get_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(options=options)


def run():
    searches = load_json("searches.json")
    seen = load_json("seen_parts.json")

    driver = get_driver()

    new_items = []
    cheaper_items = []
    price_added_items = []

    print(f"Loaded searches: {len(searches)}")

    for search in searches:
        name = search["name"]
        url = search["url"]
        max_price = search.get("max_price")

        print(f"Running search: {name}")
        print(f"URL: {url}")
        print(f"Max price: {max_price}")

        driver.get(url)
        time.sleep(3)

        links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/ID-']")
        links = list({l.get_attribute("href") for l in links})

        print(f"[{name}] Found engines: {len(links)}")

        if name not in seen:
            seen[name] = {}

        for i, link in enumerate(links[:MAX_RESULTS]):
            print(f"[{name}] Checking detail {i+1}/{len(links)}")

            driver.get(link)
            time.sleep(1.5)

            body_text = driver.find_element(By.TAG_NAME, "body").text
            price = extract_price(body_text)

            if price is None:
                print(f"[{name}] ⚠️ Price not found, skipping: {link}")
                continue

            if max_price and price > max_price:
                print(f"[{name}] Skipping over max_price: {price} {link}")
                continue

            part_id = link.split("ID-")[-1]

            old_price = seen[name].get(part_id)

            # NEW
            if part_id not in seen[name]:
                new_items.append((name, part_id, price, link))

            # CHEAPER
            elif old_price and price < old_price:
                cheaper_items.append((name, part_id, old_price, price, link))

            # PRICE ADDED LATER
            elif old_price is None and price:
                price_added_items.append((name, part_id, price, link))

            seen[name][part_id] = price

    save_json("seen_parts.json", seen)

    print(f"New engines: {len(new_items)}")
    print(f"Cheaper engines: {len(cheaper_items)}")
    print(f"Price added later: {len(price_added_items)}")

    # EMAIL (simple print for now)
    if new_items or cheaper_items or price_added_items:
        print("\n=== EMAIL ===")

        if new_items:
            print("\nNEW:")
            for item in new_items:
                print(item)

        if cheaper_items:
            print("\nCHEAPER:")
            for item in cheaper_items:
                print(item)

        if price_added_items:
            print("\nPRICE ADDED:")
            for item in price_added_items:
                print(item)

        print("\nEmail sent")


if __name__ == "__main__":
    run()
