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
    """Return a dict of { slot_name: { station_name: [meal-dicts] } } for one café."""
    url = BASE.format(slug=slug, date=day)
    print(f"    • {slug} → {url}")
    resp = requests.get(url); resp.raise_for_status()
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
        seen       = {}   # seen[(station_name)] = set of (meal, price)
        current_station = None
        current_meal    = None

        # Walk in document order, grouping toppings under their meal
        for el in section.find_all(["h3", "header"], recursive=True):
            # Station header?
            if el.name=="h3" and "site-panel__daypart-station-title" in el.get("class", []):
                current_station = tidy(el.get_text())
                station_map.setdefault(current_station, [])
                seen[current_station] = set()
                current_meal = None

            # Menu-item header?
            elif el.name=="header" and "site-panel__daypart-item-header" in el.get("class", []):
                name_el  = el.select_one("button.site-panel__daypart-item-title")
                price_el = el.select_one("div.site-panel__daypart-item-price")
                if not name_el:
                    continue
                name  = tidy(name_el.get_text())
                price = tidy(price_el.text) if price_el else ""

                # priced ⇒ new meal
                if price:
                    key = (name, price)
                    if key not in seen[current_station]:
                        seen[current_station].add(key)
                        current_meal = {"meal": name, "price": price, "toppings": []}
                        station_map[current_station].append(current_meal)
                    else:
                        current_meal = None

                # no price ⇒ it’s a topping/extra for the last meal
                else:
                    if current_meal:
                        current_meal["toppings"].append(name)

        cafe_menu[slot_nm] = station_map

    return cafe_menu

# ——————————————————————————————————————————————————————————————————————————————
def scrape_all(day: str=None) -> dict:
    d = (day or date.today().isoformat()).rstrip("/") + "/"
    full = {"date": d.rstrip("/"), "time_slots": {}}
    cond_buffer = []  # hold (cafe_name, slot_nm, station_map) for Condiments tabs

    for slug in CAFE_SLUGS:
        cafe_name = slug.replace("-", " ").title()
        cafe_data = scrape_cafe(slug, d)

        # If a page ONLY has one tab and it’s literally the café’s name,
        # shove it into “All Day”
        if len(cafe_data)==1 and next(iter(cafe_data)).lower().startswith(cafe_name.lower()):
            single_map = next(iter(cafe_data.values()))
            parent = "All Day"
            full["time_slots"].setdefault(parent, {})[cafe_name] = single_map
            continue

        # Otherwise, sort tabs into normal vs condiments/extras
        for slot_nm, station_map in cafe_data.items():
            if "Condiments" in slot_nm or "Extras" in slot_nm:
                cond_buffer.append((cafe_name, slot_nm, station_map))
            else:
                # regular time slot
                ts = full["time_slots"].setdefault(slot_nm, {})
                ts[cafe_name] = station_map

    # — process all Condiments/Extras tabs now ——————————————————————————
    for cafe_name, slot_nm, station_map in cond_buffer:
        # find which parent slot this condiment tab belongs to:
        if "Breakfast" in slot_nm:
            parent = next(k for k in full["time_slots"] if k.startswith("Breakfast"))
        elif "Lunch" in slot_nm:
            parent = next(k for k in full["time_slots"] if k.startswith("Lunch"))
        else:
            # fallback: lump into All Day
            parent = "All Day"
            full["time_slots"].setdefault(parent, {})

        cafe_entry = full["time_slots"][parent].setdefault(cafe_name, {})
        condiments = {}
        extras     = {}

        for station, items in station_map.items():
            # if station ends with the parent label → condiments
            if station.lower().endswith(parent.lower()):
                rest = tidy(station[: -len(parent)])
                condiments[rest] = [itm["meal"] for itm in items]
            else:
                extras[station] = [itm["meal"] for itm in items]

        if condiments:
            cafe_entry["condiments"] = condiments
        if extras:
            cafe_entry["extras"] = extras

    return full

# ——————————————————————————————————————————————————————————————————————————————
if __name__=="__main__":
    target = sys.argv[1] if len(sys.argv)>1 else None
    data = scrape_all(target)

    with open("full_menu.json","w") as f:
        json.dump(data, f, indent=2)

    # summary
    total = sum(
        len(meals)
        for slot in data["time_slots"].values()
        for cafe in slot.values()
        for _, meals in cafe.items()
        if isinstance(meals, list)
    )
    print(f"\n✓ Scraped {len(CAFE_SLUGS)} cafés, ~{total} meals → full_menu.json")
