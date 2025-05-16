#!/usr/bin/env python3
import sys
import json
import requests
from bs4 import BeautifulSoup
from datetime import date

BASE_URL = "https://scudining.cafebonappetit.com/cafe/marketplace-2/"

def scrape_menu(target_date=None):
    # Build URL suffix (e.g. "2025-05-16/")
    if target_date:
        ds = target_date.rstrip("/") + "/"
    else:
        ds = date.today().isoformat() + "/"
    url = BASE_URL + ds
    print(f"→ Scraping {url}")

    # Fetch and parse
    resp = requests.get(url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Discover all day-part tabs
    tabs = []
    for btn in soup.select("a.jump-nav__btn"):
        tabs.append({
            "id":   btn["data-target"],
            "name": btn.get_text(strip=True)
        })

    # Gather items under each tab
    result = {
        "location": "Benson",
        "date":     ds.rstrip("/"),
        "menus":    {}
    }
    total_count = 0

    for tab in tabs:
        section = soup.find("section", id=tab["id"])
        items = []
        if section:
            for hdr in section.select("header.site-panel__daypart-item-header"):
                name_el  = hdr.select_one("button.site-panel__daypart-item-title")
                price_el = hdr.select_one("div.site-panel__daypart-item-price")
                if name_el and price_el:
                    meal_name = name_el.get_text(strip=True)
                    price     = price_el.get_text(strip=True)
                    items.append({
                        "meal":  meal_name,
                        "price": price
                    })
                    total_count += 1
        result["menus"][tab["name"]] = items

    return result, total_count

if __name__ == "__main__":
    # Optionally pass a date (YYYY-MM-DD) on the command line
    target = sys.argv[1] if len(sys.argv) > 1 else None
    data, count = scrape_menu(target)

    # 1) Print a quick console report
    for name, items in data["menus"].items():
        print(f"\n{name} ({len(items)} items)")
        for itm in items:
            print(f"  • {itm['meal']} — ${itm['price']}")

    # 2) Write out to JSON
    with open("scraped_menu.json", "w") as f:
        json.dump(data, f, indent=2)
    print(f"\n✔ Saved {count} total items to scraped_menu.json")
