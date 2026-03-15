import os
import smtplib
from email.mime.text import MIMEText

import requests
from bs4 import BeautifulSoup

URL = "https://www.bildelsbasen.se/sv-se/pb/S%C3%B6k/Bildelar/s6/Motor/Motor-Diesel/Alla?query=R9M&limit=100"

EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASS = os.environ.get("EMAIL_PASS")


def fetch_results():
    r = requests.get(URL, timeout=30)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    results = []

    for link in soup.select("a[href*='/part/']"):
        title = link.get_text(strip=True)
        href = link.get("href")

        if title and href:
            full_url = "https://www.bildelsbasen.se" + href
            results.append((title, full_url))

    return results


def send_email(results):
    if not EMAIL_USER or not EMAIL_PASS:
        print("EMAIL_USER või EMAIL_PASS puudub")
        return

    if not results:
        body = "Ühtegi tulemust ei leitud."
    else:
        lines = ["Leitud R9M mootorid Bildelsbasenis:\n"]
        for title, url in results[:20]:
            lines.append(f"{title}\n{url}\n")
        body = "\n".join(lines)

    msg = MIMEText(body, _charset="utf-8")
    msg["Subject"] = "R9M test email"
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_USER

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)

    print("Email sent")


def main():
    results = fetch_results()
    print(f"Found {len(results)} results")
    send_email(results)


if __name__ == "__main__":
    main()
