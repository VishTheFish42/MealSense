import json, pathlib

payloads = [json.loads(p.read_text()) for p in pathlib.Path("menus").glob("*.json")]
json.dump(payloads, open("menus_all.json","w"), indent=2)