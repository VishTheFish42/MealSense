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

# -------- 2)  Helpers -------------------------------------------------
def tidy(txt):            # strip + squeeze whitespace
    return re.sub(r"\s+", " ", txt).strip()

def get_time_slot(btn):
    """Return a nice label like 'Brunch — 10:00 AM-2:30 PM'
       If no hours are listed, fallback to the tab's text."""
    label = tidy(btn.get_text())
    hrs   = btn.get("data-hours") or ""
    hrs   = tidy(hrs.replace("|", "—"))
    return f"{label} — {hrs}" if hrs else label

def scrape_cafe(slug: str, day: str):
    url = BASE.format(slug=slug, date=day)
    print(f"  · {slug}")
    html = requests.get(url).text
    soup = BeautifulSoup(html, "html.parser")

    # discover every day-part button
    tabs = soup.select("a.jump-nav__btn")
    cafe_data = {}

    for btn in tabs:
        slot_id = btn["data-target"]

        if slot_id in SKIP_TABS:
            continue
            
        print(f"    → {slot_id}")

        slot_nm = get_time_slot(btn)
        section = soup.find("section", id=slot_id)
        if not section:
            continue

        time_slot = cafe_data.setdefault(slot_nm, {})
        current_station = "Unknown"

        # walk H3 (station) and HEADER (item) in order
        for el in section.find_all(["h3", "header"], recursive=True):
            if "site-panel__daypart-station-title" in el.get("class", []):
                current_station = tidy(el.get_text())
                time_slot.setdefault(current_station, [])
            elif "site-panel__daypart-item-header" in el.get("class", []):
                name_el  = el.select_one("button.site-panel__daypart-item-title")
                price_el = el.select_one("div.site-panel__daypart-item-price")
                if name_el and price_el:
                    time_slot.setdefault(current_station, []).append({
                        "meal":  tidy(name_el.get_text()),
                        "price": tidy(price_el.get_text().replace("reg.", "")),
                    })
    return cafe_data

# -------- 3)  Main routine -------------------------------------------
def scrape_all(day=None):
    day = (day or date.today().isoformat()).rstrip("/") + "/"
    full = {"date": day.rstrip("/"), "time_slots": {}}

    for slug in CAFE_SLUGS:
        cafe_menu = scrape_cafe(slug, day)
        for slot, stations in cafe_menu.items():
            slot_dict = full["time_slots"].setdefault(slot, {})
            slot_dict[slug.replace("-", " ").title()] = stations  # café name

    return full

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    data   = scrape_all(target)

    with open("full_menu.json", "w") as f:
        json.dump(data, f, indent=2)
    total = sum(
        len(items)
        for ts in data["time_slots"].values()
        for cafe in ts.values()
        for items in cafe.values()
    )
    print(f"\n✓ Scraped {len(CAFE_SLUGS)} cafés, {total} menu items → full_menu.json")
