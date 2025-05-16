#!/usr/bin/env python3
import sys
import json
import requests
from bs4 import BeautifulSoup
from datetime import date

BASE_URL = "https://scudining.cafebonappetit.com/cafe/marketplace-2/"

def scrape_menu(target_date=None):
    # build URL
    if target_date:
        # expect e.g. "2025-05-16" or "2025-05-16/"
        ds = target_date.rstrip("/") + "/"
    else:
        ds = date.today().isoformat() + "/"
    url = BASE_URL + ds
    print(f"→ Scraping {url}")

    # fetch & parse
    resp = requests.get(url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # find all tab buttons to get their IDs and labels
    tabs = []
    for btn in soup.select("a.jump-nav__btn"):
        tabs.append({
            "id":   btn["data-target"],
            "name": btn.get_text(strip=True)
        })

    # collect items under each tab
    result = {
        "location": "Benson",
        "date":     ds.rstrip("/"),
        "menus":    {}
    }

    for tab in tabs:
        section = soup.find("section", id=tab["id"])
        items = []
        if section:
            for hdr in section.select("header.site-panel__daypart-item-header"):
                name_el  = hdr.select_one("button.site-panel__daypart-item-title")
                price_el = hdr.select_one("div.site-panel__daypart-item-price")
                if not name_el or not price_el:
                    continue
                items.append({
                    "meal":  name_el.get_text(strip=True),
                    "price": price_el.get_text(strip=True)
                })
        result["menus"][tab["name"]] = items

    return result

if __name__ == "__main__":
    menu = scrape_menu()
    print(menu)
