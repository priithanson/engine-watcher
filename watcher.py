import os
import smtplib
from email.mime.text import MIMEText

import requests
from bs4 import BeautifulSoup

URL = "https://www.bildelsbasen.se/sv-se/pb/S%C3%B6k/Bildelar/s6/Motor/Motor-Diesel/Alla?query=R9M&limit=100"

EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASS = os.environ.get("EMAIL_PASS")


def fetch_results():

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    r = requests.get(URL, headers=headers, timeout=30)
    soup = BeautifulSoup(r.text, "html.parser")

    results = []

    for a in soup.find_all("a", href=True):

        href = a["href"]

        if "/part/" in href:

            title = a.get_text(strip=True)

            if title:

                url = "https://www.bildelsbasen.se" + href
                results.append((title, url))

    return results


def send_email(results):

    if not EMAIL_USER or not EMAIL_PASS:
        print("Email secrets missing")
        return

    lines = ["R9M mootorid Bildelsbasenis:\n"]

    for title, url in results[:20]:

        lines.append(f"{title}\n{url}\n")

    body = "\n".join(lines)

    msg = MIMEText(body, _charset="utf-8")
    msg["Subject"] = "R9M mootorid"
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_USER

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:

        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)

    print("Email sent")


def main():

    print("Checking Bildelsbasen...")

    results = fetch_results()

    print("Found engines:", len(results))

    send_email(results)


if __name__ == "__main__":
    main()
