#!/usr/bin/env python3
"""
Scrape *all* SCU campus cafés for a single day
Outputs: full_menu.json (see structure above)
"""
import json, re, sys
from datetime import date
from bs4 import BeautifulSoup
import requests

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

# -->  NEW  ---------------------------------------------------------------
#   1.  While scraping *any* café we build this on the fly so we know
#       which words are definitely condiments and which are “base” items
CONDIMENT_SET : set[str] = set()

# ❶  Everything in this set is *always* treated as a topping/side
ALWAYS_CONDIMENTS = {
    # breakfast proteins & sides  …                         (unchanged)
    "scrambled eggs", "whole cracked egg", "egg white", "just eggs (plant-based)",
    "bacon", "ham", "canadian bacon", "sausage", "chicken apple sausage",
    "tater tots", "hash browns", "home fries",

    # bowls / toast-bar fruit & sweet toppings  …           (unchanged)
    "strawberry", "blueberries", "blackberries", "raspberry",
    "cantaloupe", "honeydew", "pineapple", "banana", "granola",
    "chocolate chips", "shredded coconut",

    # ❶  wrap / bread *variants* that only appear as choices
    "wheat tortilla", "spinach tortilla", "flour tortilla",
    "corn tortilla",  "spinach wrap",    "whole-wheat wrap",
}

# ❷  Items that *can* be a zero-price entrée (leave eggs, bacon, etc. out)
_WORDS_THAT_ARE_MEALS = {
    "yogurt", "bagel", "bread", "toast",
    "tortilla", "crepe", "omelet", "burrito",
    "pancake", "waffle", "bowl", "salad",
}
# ----------——— helpers ————————————————————————————————————————————————————————
def tidy(txt: str) -> str:
    """Trim and collapse whitespace."""
    return re.sub(r"\s+", " ", txt).strip()

def looks_like_condiment(name: str) -> bool:
    n = name.lower()

    # 1. explicit list  (fast, authoritative)
    if n in ALWAYS_CONDIMENTS:
        return True

    # 2. “Add …” or “+ …”  => topping
    if n.startswith(("add ", "+")):
        return True

    # 3. keyword pattern  (unchanged from earlier)
    if re.fullmatch(r"[a-z ]+", n) and any(
        kw in n
        for kw in (
            "salsa", "sauce", "cheese", "chips", "granola",
            "guacamole", "onion", "cilantro", "lime", "jalapeno",
            "pepper", "tomato", "spinach", "mushroom",
            "chocolate", "coconut",
        )
    ):
        return True

    return False

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

            # ——————————————————— MENU-ITEM HEADER ——————————————————————
            elif el.name=="header" and "site-panel__daypart-item-header" in el["class"]:
                name  = tidy(el.select_one("button.site-panel__daypart-item-title").get_text())
                price = tidy(el.select_one("div.site-panel__daypart-item-price").text) if el.select_one("div.site-panel__daypart-item-price") else ""

                is_priced = price and price != "0"

                # ---------- A)  Priced  → always a brand-new meal ----------
                if is_priced:
                    key = (name, price)
                    if key not in seen[current_station]:
                        current_meal = {"meal": name, "price": price, "toppings": []}
                        station_map[current_station].append(current_meal)
                        seen[current_station].add(key)
                    else:
                        current_meal = None

                # ---------- B)  Un-priced  → decide meal vs topping ----------
                else:
                    if current_meal and looks_like_condiment(name):
                        current_meal["toppings"].append(name)
                    else:
                        current_meal = {"meal": name, "price": "", "toppings": []}
                        station_map[current_station].append(current_meal)

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

       #  Collect condiment/extras tabs so we can merge later
        for slot_nm, station_map in cafe_data.items():
            if re.search(r"(condiment|extra)s?", slot_nm, re.I):
                cond_buffer.append((cafe_name, slot_nm, station_map))
            else:
                full["time_slots"].setdefault(slot_nm, {})[cafe_name] = station_map

     # ——— 2)  Fold the “Condiments / Extras” tabs back in  ————————
    for cafe_name, slot_nm, station_map in cond_buffer:
        parent_slot = (
            next((k for k in full["time_slots"] if k.startswith("Breakfast") and "Breakfast" in slot_nm), None)
            or next((k for k in full["time_slots"] if k.startswith("Lunch")      and "Lunch"      in slot_nm), None)
            or "All Day"
        )
        cafe_entry = full["time_slots"].setdefault(parent_slot, {}).setdefault(cafe_name, {})

        for station, items in station_map.items():
            conds = [itm["meal"] for itm in items]
            CONDIMENT_SET.update(x.lower() for x in conds)         #  teach the scraper

            # attach to *first* meal in that same station (creates one if none)
            if station not in cafe_entry:
                cafe_entry[station] = [{
                    "meal": station,
                    "price": "",
                    "toppings": conds
                }]
            else:
                target_meal = next(
                    (itm for itm in cafe_entry[station] if not looks_like_condiment(itm["meal"])),
                    None,
                )

                # if the station had only condiments, fabricate a placeholder
                if target_meal is None:
                    target_meal = {"meal": station, "price": "", "toppings": []}
                    cafe_entry[station].insert(0, target_meal)

                target_meal["toppings"].extend(
                    x for x in conds if x not in target_meal["toppings"]
                )

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
