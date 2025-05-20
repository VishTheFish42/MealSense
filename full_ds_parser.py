# menu_parser.py  — 2nd revision  (2025‑05‑19)
"""Parse one *or many* Transact Campus "getmenu" JSON blobs ⇒ flat CSVs
-----------------------------------------------------------------------
Key features requested by the client (Victor):
  ✔  capture *all* option / modifier trees
  ✔  keep the `is_hidden` flag for production‑toggle logic
  ✔  preserve the first‑online datetime so a once‑per‑day crawl is safe
  ✔  parse n JSON files in one call and tag rows with `restaurant`

Outputs
•••••••
* **foods.csv** – 1 row per base item (name, macros, price, flags …)
* **options.csv** – exploded modifiers (itemid × option_group × value)
* **availability.csv** – item × schedule mapping for meal‑period queries

Usage (CLI)
-----------
$ python menu_parser.py  jsons/*.json  --outdir data  --map benson=6212 sudi=6213

If you omit the --map flag the script infers `restaurant` from each
filename (substring before first “_”).
"""

from __future__ import annotations

import argparse
import json
import os
import glob
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

import pandas as pd

# ──────────────────────────────────────────────────────────────────────────────
# Core public helper
# ──────────────────────────────────────────────────────────────────────────────

def parse_many(
    json_dir: Sequence[Path | str],
    *,
    restaurant_map: Dict[str, str] | None = None,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Parse multiple Transact menu blobs and return 3 normalised dataframes.

    Parameters
    ----------
    json_paths : list[str|Path]
        Files produced by *mobileorderprodapi* /api_user/getmenu.
    restaurant_map : dict[str,str], optional
        Map a filename‑stem (or slug) → human restaurant label.  If omitted the
        stem of each file (text before first "_") is used.

    Returns
    -------
    foods_df, options_df, availability_df
    """

    food_rows: list[dict[str, Any]] = []
    opt_rows: list[dict[str, Any]] = []
    avail_rows: list[dict[str, Any]] = []

    # print(glob.glob(os.path.join(json_dir, "*.json")))
    for path in glob.glob(os.path.join(json_dir, "*.json")):
        path = Path(path)
        with path.open("r", encoding="utf-8") as fp:
            raw = json.load(fp)

        rest_key = path.stem.split("_")[0]
        restaurant = (
            restaurant_map.get(rest_key, rest_key) if restaurant_map else rest_key
        )

        _foods, _opts, _av = _parse_one(raw, restaurant)
        food_rows.extend(_foods)
        opt_rows.extend(_opts)
        avail_rows.extend(_av)

    foods_df = pd.DataFrame(food_rows).drop_duplicates("itemid").reset_index(drop=True)
    options_df = pd.DataFrame(opt_rows).drop_duplicates().reset_index(drop=True)
    availability_df = (
        pd.DataFrame(avail_rows).drop_duplicates().reset_index(drop=True)
    )

    return foods_df, options_df, availability_df


# ──────────────────────────────────────────────────────────────────────────────
# Internal – single‑blob parser
# ──────────────────────────────────────────────────────────────────────────────

def _parse_one(raw: dict, restaurant: str):
    menu = raw.get("menu", {})
    sections: List[Dict[str, Any]] = menu.get("sections_1", []) + menu.get(
        "sections_2", []
    )

    foods: list[dict[str, Any]] = []
    opts: list[dict[str, Any]] = []
    avs: list[dict[str, Any]] = []

    for sec in sections:
        sec_name = sec.get("name", "").strip()
        sec_sched_name = sec.get("currently_available_qp_schedule_name") or None
        sec_sched_ids = sec.get("scheduleids") or []

        for item in sec.get("items", []):
            itemid = item.get("itemid")
            is_hidden = bool(item.get("is_hidden"))
            online_dt = _to_dt(item.get("manual_online_datetime"))

            foods.append(
                {
                    "restaurant": restaurant,
                    "section": sec_name,
                    "itemid": itemid,
                    "name": item.get("qp_name") or item.get("name"),
                    "description": item.get("description"),
                    "price_base_c": item.get("price_base"),
                    "price_disp_c": item.get("price_display"),
                    # nutrition (may be 0 if missing):
                    "calories": item.get("nutrition_calories"),
                    "fat_g": item.get("nutrition_fat"),
                    "protein_g": item.get("nutrition_protein"),
                    "carb_g": item.get("nutrition_carbohydrates"),
                    "fiber_g": item.get("nutrition_fiber"),
                    "sugar_g": item.get("nutrition_sugar"),
                    "cholesterol_mg": item.get("nutrition_cholesterol"),
                    "sodium_mg": item.get("nutrition_sodium"),
                    # flags / timing
                    "is_hidden": is_hidden,
                    "manual_online_datetime": online_dt,
                    "currently_available": bool(item.get("mobile_stock_available")),
                }
            )

            # ╭─ modifiers / options ─╮
            for opt_group in item.get("options", []):
                if opt_group.get("is_hidden"):
                    continue
                gname = opt_group.get("name")
                gmax = opt_group.get("maximum", 1)
                for val in opt_group.get("values", []):
                    if val.get("is_hidden"):
                        continue
                    opts.append(
                        {
                            "restaurant": restaurant,
                            "itemid": itemid,
                            "option_group": gname,
                            "max_select": gmax,
                            "value": val.get("name"),
                            "value_price_c": val.get("price"),
                        }
                    )

            # ╭─ availability rows ─╮
            combined_scheds = sec_sched_ids + (item.get("scheduleids") or [])
            combined_scheds = combined_scheds or [None]
            for sid in combined_scheds:
                avs.append(
                    {
                        "restaurant": restaurant,
                        "itemid": itemid,
                        "scheduleid": sid,
                        "section": sec_name,
                        "section_schedule_name": sec_sched_name,
                    }
                )

    return foods, opts, avs


def _to_dt(s: str | None):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.strip())
    except ValueError:
        return None


# ──────────────────────────────────────────────────────────────────────────────
# CLI – one‑shot parse & save
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Flatten Transact Campus menu JSON → CSVs (foods, options, availability)"
    )
    ap.add_argument(
        "json_dir",
        help="dir with jsons",
    )
    ap.add_argument("--outdir", default="out", help="directory for CSVs")
    ap.add_argument(
        "--map",
        nargs="*",
        metavar="slug=Restaurant Name",
        help="Optional mapping from filename stem to display name",
    )
    ns = ap.parse_args()

    mapping = dict(split.split("=", 1) for split in ns.map) if ns.map else None
    foods, opts, avs = parse_many(ns.json_dir, restaurant_map=mapping)

    out = Path(ns.outdir)
    out.mkdir(parents=True, exist_ok=True)
    foods.to_csv(out / "foods.csv", index=False)
    opts.to_csv(out / "options.csv", index=False)
    avs.to_csv(out / "availability.csv", index=False)

    print(
        f"✔ wrote {len(foods):,} foods, {len(opts):,} options, "
        f"{len(avs):,} availability rows → {out}"
    )
