"""
Adapter for the CSV upload path described in README.md §7.2.

Required columns: name, station, meal_period, available_from, available_until,
served_on, calories, protein_g, carbs_g, fat_g, fiber_g, sodium_mg, sugar_g,
price, allergens (pipe-separated), dietary_tags (pipe-separated), ingredients
(pipe-separated).

Allergen safety: a CSV has no way to represent "field absent" vs "field
present but blank" other than the column existing at all. So: if the
`allergens` column is missing from the header entirely, every row in that
file is rejected (the source gives us no allergen signal at all). If the
column exists but a specific row's cell is blank, that's treated as an
explicit "no allergens" for that item, not missing data.
"""
from __future__ import annotations
import csv
import io

from .base import IngestionResult, RejectedRecord
from .schema import MenuItemValidationError, build_menu_item, stable_item_id


def _split_pipes(value: str | None) -> list[str]:
    if not value or not value.strip():
        return []
    return [v.strip() for v in value.split("|") if v.strip()]


class CsvMenuAdapter:
    def normalize(self, raw: str) -> IngestionResult:
        result = IngestionResult()
        reader = csv.DictReader(io.StringIO(raw))
        has_allergen_column = reader.fieldnames is not None and "allergens" in reader.fieldnames

        for row in reader:
            try:
                allergens = _split_pipes(row.get("allergens")) if has_allergen_column else None
                item = build_menu_item(
                    id=stable_item_id(row.get("name", ""), row.get("station", "")),
                    name=row.get("name", ""),
                    station=row.get("station"),
                    meal_period=(row.get("meal_period") or "").strip(),
                    available_from=row.get("available_from") or None,
                    available_until=row.get("available_until") or None,
                    calories=row.get("calories"),
                    protein_g=row.get("protein_g"),
                    carbs_g=row.get("carbs_g"),
                    fat_g=row.get("fat_g"),
                    fiber_g=row.get("fiber_g"),
                    sodium_mg=row.get("sodium_mg"),
                    sugar_g=row.get("sugar_g"),
                    price=row.get("price"),
                    allergens=allergens,
                    dietary_tags=_split_pipes(row.get("dietary_tags")),
                    ingredients=_split_pipes(row.get("ingredients")),
                )
                result.items.append(item)
            except MenuItemValidationError as e:
                result.rejected.append(RejectedRecord(raw=row, reason=str(e)))

        return result
