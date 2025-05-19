import json, pprint, json

def dollars(cents):            # helper to show “525” → 5.25
    return None if cents in (None,0) else round(cents/100,2)

j = json.load(open("menus/mobileorderprodapi.transactcampus.com_1747628377.json"))
menu_root = j["menu"]    
sections = menu_root["sections_1"]

simple_menu = {}

for s in sections:
    if s.get("is_hidden"):                # skip hidden sections
        continue
    sect_name = s["name"].strip()
    simple_menu.setdefault(sect_name, [])

    for itm in s["items"]:
        if itm.get("is_hidden"):          # skip hidden items
            continue

        entry = {
            "item":  itm["name"].strip(),
            "price": dollars(itm["price_display"]),
            "cal":   itm.get("cals_display", 0),
            "options": []
        }

        # pull the choice sets (“Drink Size”, “Milk Options”, …)
        for opt in itm.get("options", []):
            if opt.get("is_hidden"):      # skip hidden option groups
                continue
            opt_block = {
               "name":   opt["name"],
               "max":    opt.get("maximum",1),
               "values": [
                   {
                     "value": v["name"],
                     "price": dollars(v["price"])
                   }
                   for v in opt["values"] if not v.get("is_hidden")
               ]
            }
            entry["options"].append(opt_block)

        simple_menu[sect_name].append(entry)

pprint.pprint(simple_menu["Drinks"][:2])        # peek
json.dump(simple_menu, open("menu_simplified.json","w"), indent=2)

print(len(simple_menu["Pastries and Baked Goods"]))