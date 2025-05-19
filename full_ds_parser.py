import json
from datetime import datetime
from pathlib import Path
from typing import Tuple, List, Dict, Any

import pandas as pd


###############################################################################
# Public helpers – you will mainly interact with `parse_menu()`
###############################################################################

def parse_menu(json_path_or_obj) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Parse the Transact Campus Fresh Bytes menu JSON.

    Parameters
    ----------
    json_path_or_obj : str | Path | dict
        Either a path/str pointing to the raw *mobileorderprodapi* json file or an
        already-loaded Python object.

    Returns
    -------
    foods_df : pd.DataFrame
        One row per *menu_item* with all nutrition + commercial metadata that is
        present in the feed.  Suitable for ML / embeddings.

    availability_df : pd.DataFrame
        Normalised availability table mapping an itemid to every schedule it
        belongs to, the section name (often corresponds to meal period), and
        the window in which that schedule is marked *currently_available* in
        the feed.
    """

    # ---------------------------------------------------------------------
    # 1.  Load JSON
    # ---------------------------------------------------------------------
    if isinstance(json_path_or_obj, (str, Path)):
        with open(json_path_or_obj, "r", encoding="utf-8") as fp:
            raw = json.load(fp)
    else:
        raw = json_path_or_obj  # assume already‑parsed

    menu = raw.get("menu", {})

    # Menu feed uses two parallel arrays (sections_1, sections_2). Join them.
    sections: List[Dict[str, Any]] = menu.get("sections_1", []) + menu.get(
        "sections_2", []
    )

    # ---------------------------------------------------------------------
    # 2.  Core item extraction
    # ---------------------------------------------------------------------
    food_records: List[Dict[str, Any]] = []
    availability_records: List[Dict[str, Any]] = []

    for sec in sections:
        sec_name = sec.get("name")
        sec_sched_name = sec.get("currently_available_qp_schedule_name") or None
        sec_sched_ids = sec.get("scheduleids") or []

        for item in sec.get("items", []):
            rec: Dict[str, Any] = {
                # primary keys
                "itemid": item.get("itemid"),
                "name": item.get("qp_name") or item.get("name"),
                "description": item.get("description"),

                # commercial
                "price_base": item.get("price_base"),
                "price_display": item.get("price_display"),
                "cover_picture_url": item.get("cover_picture_url"),

                # nutrition
                "calories": item.get("nutrition_calories"),
                "fat_g": item.get("nutrition_fat"),
                "protein_g": item.get("nutrition_protein"),
                "carb_g": item.get("nutrition_carbohydrates"),
                "fiber_g": item.get("nutrition_fiber"),
                "sugar_g": item.get("nutrition_sugar"),
                "cholesterol_mg": item.get("nutrition_cholesterol"),
                "sodium_mg": item.get("nutrition_sodium"),

                # availability meta
                "section": sec_name,
                "section_schedule_name": sec_sched_name,
                "section_scheduleids": sec_sched_ids,
                "item_scheduleids": item.get("scheduleids") or [],
                "manual_online_datetime": _parse_date(item.get("manual_online_datetime")),
                "currently_available": bool(item.get("mobile_stock_available", 0) and item.get("is_hidden", 0) == 0),
            }
            food_records.append(rec)

            # explode availability rows for easier joins later
            combined_scheds = (
                rec["section_scheduleids"] + rec["item_scheduleids"] or [None]
            )
            if not combined_scheds:
                combined_scheds = [None]

            for sid in combined_scheds:
                availability_records.append(
                    {
                        "itemid": rec["itemid"],
                        "scheduleid": sid,
                        "section": sec_name,
                        "section_schedule_name": sec_sched_name,
                    }
                )

    foods_df = pd.DataFrame(food_records).drop_duplicates("itemid")
    availability_df = pd.DataFrame(availability_records).drop_duplicates()

    return foods_df, availability_df


###############################################################################
# Internal utilities
###############################################################################

def _parse_date(date_str: str | None):
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.strip())
    except ValueError:
        return None


###############################################################################
# CLI helper for quick‑n‑dirty runs
###############################################################################
if __name__ == "__main__":
    import argparse, sys

    ap = argparse.ArgumentParser(description="Parse Transact menu feed → CSVs")
    ap.add_argument("--json", help="Path to mobileorderprodapi*.json file")
    ap.add_argument("--json_dir", help="Path to mobileorderprodapi*.json file")
    ap.add_argument("--outdir", default="out", help="Output directory")
    ns = ap.parse_args()

    if ns.json_dir:
        # aggregate all JSON files in the directory
        json_files = list(Path(ns.json_dir).glob("*.json"))
        if not json_files:
            print(f"No JSON files found in {ns.json_dir}")
            sys.exit(1)
        ns.json = json_files
        
    for f in json_files:
        print(f"Parsing {f}")
        foods, avail = parse_menu(f)
        outdir = Path(ns.outdir) / f.stem
        outdir.mkdir(parents=True, exist_ok=True)

        foods.to_csv(outdir / "foods.csv", index=False)
        avail.to_csv(outdir / "availability.csv", index=False)

    print(f"Wrote {len(foods):,} foods and {len(avail):,} availability rows → {outdir}")
