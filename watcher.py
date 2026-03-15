import requests
from bs4 import BeautifulSoup

URL = "https://www.bildelsbasen.se/sv-se/pb/S%C3%B6k/Bildelar/s6/Motor/Motor-Diesel/Alla?query=R9M&limit=100"

print("Checking Bildelsbasen...")

r = requests.get(URL)

soup = BeautifulSoup(r.text, "html.parser")

results = []

for link in soup.select("a[href*='/part/']"):

    title = link.get_text(strip=True)

    if title:

        url = "https://www.bildelsbasen.se" + link["href"]

        results.append((title, url))


print("Found engines:", len(results))

for title, url in results[:10]:

    print(title)

    print(url)

    print("------")
