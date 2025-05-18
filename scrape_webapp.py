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

    # url = BASE_URL + ds
    url = BASE_URL
    print(f"→ Scraping {url}")

    resp = requests.get(url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # 1) discover all day-part tabs
    tabs = [
        {"id": btn["data-target"], "name": btn.get_text(strip=True)}
        for btn in soup.select("a.jump-nav__btn")
    ]

    result = {
        "location": "Benson",
        "date":     ds.rstrip("/"),
        "menus":    {}
    }
    total_count = 0

    for tab in tabs:
        section = soup.find("section", id=tab["id"])
        station_items = {}
        current_station = None

        if section:
            # walk through all station headers and item headers in document order
            for el in section.find_all(["h3", "header"], recursive=True):
                # when we hit a station title, update current_station
                if (el.name == "h3"
                    and "site-panel__daypart-station-title" in el.get("class", [])):
                    current_station = el.get_text(strip=True)
                    station_items.setdefault(current_station, [])
                # when we hit an item header, scrape name+price into current_station
                elif (el.name == "header"
                      and "site-panel__daypart-item-header" in el.get("class", [])):
                    if current_station is None:
                        # fallback if no station seen yet
                        current_station = "Unknown"
                        station_items.setdefault(current_station, [])
                    name_el  = el.select_one("button.site-panel__daypart-item-title")
                    price_el = el.select_one("div.site-panel__daypart-item-price")
                    if name_el and price_el:
                        meal = name_el.get_text(strip=True)
                        price = price_el.get_text(strip=True)
                        station_items[current_station].append({
                            "meal":  meal,
                            "price": price.replace("reg.", ""),
                        })
                        total_count += 1

        result["menus"][tab["name"]] = station_items

    return result, total_count

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    data, count = scrape_menu(target)

    # — console report —
    for tab_name, stations in data["menus"].items():
        print(f"\n{tab_name} ({sum(len(v) for v in stations.values())} items)")
        for station, items in stations.items():
            print(f"  [{station}]")
            for itm in items:
                print(f"    • {itm['meal']} — ${itm['price']}")

    # — write JSON —
    with open("scraped_menu_bytes.json", "w") as f:
        json.dump(data, f, indent=2)
    print(f"\n✔ Saved {count} total items to scraped_menu.json")
