#!/usr/bin/env python3
"""
Scrape *all* SCU campus cafés for a single day
Outputs: full_menu.json (see structure above)
"""
import sys, json, re, requests
from datetime import date
from bs4 import BeautifulSoup

# -------- 1)  Café slugs you want to crawl (add/remove here) ----------
CAFE_SLUGS = [
    "marketplace-2",
    "mission-bakery",
    "cadence-cyber-cafe",
    "fresh-bytes",
    "side-bar-cafe",
    "the-sunstream-cafe",
    "cellar-market",
]

SKIP_TABS = [
    "news",
    "cafe-hours",
    "food-allergies",
    "events",
    "about-your-food",
    "menu-mail",
    "contact-us",
    "chef-wars",
    "icons",
]

BASE = "https://scudining.cafebonappetit.com/cafe/{slug}/{date}/"

# ——————————————————————————————————————————————————————————————————————————————
# Helpers
def tidy(txt: str) -> str:
    """Trim and collapse whitespace."""
    return re.sub(r"\s+", " ", txt).strip()

def get_time_slot(btn):
    """Return a nice label like 'Brunch — 10:00 AM-2:30 PM'
       If no hours are listed, fallback to the tab's text."""
    label = tidy(btn.get_text())
    hrs   = tidy((btn.get("data-hours") or "").replace("|", "—"))
    return f"{label} — {hrs}" if hrs else label

# ——————————————————————————————————————————————————————————————————————————————
def scrape_cafe(slug: str, day: str) -> dict:
    """Scrape one café page, returning { time_slot: { station: [meals] } }."""
    url = BASE.format(slug=slug, date=day)
    print(f"    • fetching {slug} → {url}")
    resp = requests.get(url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    cafe_menu = {}
    tabs = soup.select("a.jump-nav__btn")

    for btn in tabs:
        slot_id = btn["data-target"]

        if slot_id in SKIP_TABS:
            continue
            
        print(f"    → {slot_id}")

        slot_nm = get_time_slot(btn)
        section = soup.find("section", id=slot_id)
        if not section:
            continue

        station_map = {}
        seen = {}  # seen[(station_name)] = set of (meal,price)
        current_station = None
        current_meal = None

        # Walk in document order to group toppings under their parent meal
        for el in section.find_all(["h3", "header"], recursive=True):
            # Station header
            if el.name == "h3" and "site-panel__daypart-station-title" in el.get("class", []):
                current_station = tidy(el.get_text())
                station_map.setdefault(current_station, [])
                seen[current_station] = set()
                current_meal = None

            # Menu-item header
            elif el.name == "header" and "site-panel__daypart-item-header" in el.get("class", []):
                name_el  = el.select_one("button.site-panel__daypart-item-title")
                price_el = el.select_one("div.site-panel__daypart-item-price")
                if not name_el:
                    continue
                name  = tidy(name_el.get_text())
                price = tidy(price_el.get_text() if price_el else "")

                # If price present → new meal
                if price:
                    key = (name, price)
                    if key not in seen[current_station]:
                        seen[current_station].add(key)
                        current_meal = {"meal": name, "price": price, "toppings": []}
                        station_map[current_station].append(current_meal)
                    else:
                        # duplicate meal+price → skip
                        current_meal = None

                # No price → this is a topping/side
                else:
                    if current_meal:
                        current_meal["toppings"].append(name)

        cafe_menu[slot_nm] = station_map

    return cafe_menu

# ——————————————————————————————————————————————————————————————————————————————
def scrape_all(day: str = None) -> dict:
    """Scrape every café for the given day (YYYY-MM-DD) or today."""
    d = (day or date.today().isoformat()).rstrip("/") + "/"
    full = {"date": d.rstrip("/"), "time_slots": {}}

    for slug in CAFE_SLUGS:
        cafe_name = slug.replace("-", " ").title()
        cafe_data = scrape_cafe(slug, d)
        for slot, stations in cafe_data.items():
            ts = full["time_slots"].setdefault(slot, {})
            ts[cafe_name] = stations

    return full

# ——————————————————————————————————————————————————————————————————————————————
if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    data   = scrape_all(target)

    # Write out full_menu.json
    with open("full_menu.json", "w") as f:
        json.dump(data, f, indent=2)

    # Summary
    total_items = sum(
        len(meals)
        for slot in data["time_slots"].values()
        for cafe in slot.values()
        for station in cafe.values()
        for meals in [station]
    )
    print(f"\n✓ Scraped {len(CAFE_SLUGS)} cafés, {total_items} unique meals → full_menu.json")
