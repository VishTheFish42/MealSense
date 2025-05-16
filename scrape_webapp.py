import requests
from bs4 import BeautifulSoup

BASE_URL = "https://scudining.cafebonappetit.com/cafe/marketplace-2/"

def scrape_menu(date_suffix=""):  # pass "2025-05-15/" etc. if you need a specific day
    url = BASE_URL + date_suffix
    resp = requests.get(url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # 1) find all the tab targets
    #    (the jump-nav buttons carry data-target="{tab-id}")
    tab_ids = [btn["data-target"] for btn in soup.select("a.jump-nav__btn")]

    report = {}

    for tab in tab_ids:
        section = soup.find("section", id=tab)
        if not section:
            continue

        # Within each section, find every food‐item header
        headers = section.select("header.site-panel__daypart-item-header")
        items = []
        for hdr in headers:
            name = hdr.select_one("button.site-panel__daypart-item-title").get_text(strip=True)
            price = hdr.select_one("div.site-panel__daypart-item-price").get_text(strip=True)
            items.append((name, price))

        report[tab] = items

    return report

if __name__ == "__main__":
    menu = scrape_menu()
    # Print a quick report
    for tab, items in menu.items():
        print(f"\n=== {tab.capitalize():<12} ({len(items)} items) ===")
        for name, price in items:
            print(f"  • {name:<40}  ${price}")
