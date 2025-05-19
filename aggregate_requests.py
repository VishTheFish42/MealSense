import json, pathlib
import argparse

parser = argparse.ArgumentParser(description="Aggregate JSON files from a directory.")
parser.add_argument("path", type=str, help="Path to the directory containing JSON files.")
args = parser.parse_args()

payloads = [json.loads(p.read_text()) for p in pathlib.Path(args.path).glob("*.json")]
json.dump(payloads, open("menus_all.json","w"), indent=2)