"""
Per-campus vendor configuration registry — the "template any college can
plug into" piece described in design-spec.md §7.0, applied to real vendor
integrations rather than just the CSV/messy-JSON fallback adapters.

Onboarding a new school that uses a vendor we already have an adapter for
(e.g. another Bon Appétit campus) means adding one CampusConfig entry here
— nothing downstream (menu_store, the recommendation engine, the admin
upload route) changes. Onboarding a school on a *different* vendor means
writing one new adapter under services/vendor_ingestion/ that exposes the
same fetch_campus_menu(campus) -> IngestionResult shape, then registering
its vendor key in routers/admin_menu.py's _VENDOR_FETCHERS map.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class CafeConfig:
    """One dining location within a campus's vendor site."""
    slug: str   # the vendor's own URL slug for this location
    name: str   # human-readable name shown to students as the item's station


@dataclass(frozen=True)
class CampusConfig:
    campus_id: str      # stable key used in API calls, e.g. ?campus=santa_clara
    display_name: str
    vendor: str         # which adapter under vendor_ingestion/ handles this feed shape
    base_url: str       # vendor site base URL for this campus
    cafes: tuple[CafeConfig, ...]


# Santa Clara University — Bon Appétit Management Co. (scudining.cafebonappetit.com).
# Café slugs and display names confirmed against the live public site
# 2026-09-11. Bon Appétit's officially documented JSON API
# (legacy.cafebonappetit.com/api/2/...) now requires vendor-issued
# credentials we don't have ("Cafemanager no longer accepts unauthenticated
# requests") — see services/vendor_ingestion/bon_appetit.py for what we use
# instead and why it's still a legitimate, if less stable, data source.
CAMPUS_CONFIGS: dict[str, CampusConfig] = {
    "santa_clara": CampusConfig(
        campus_id="santa_clara",
        display_name="Santa Clara University",
        vendor="bon_appetit",
        base_url="https://scudining.cafebonappetit.com",
        cafes=(
            CafeConfig(slug="marketplace-2", name="Benson Marketplace"),
            CafeConfig(slug="mission-bakery", name="Mission Bakery Cafe"),
            CafeConfig(slug="cellar-market", name="The Cellar Market"),
            CafeConfig(slug="fresh-bytes", name="Fresh Bytes"),
            CafeConfig(slug="feed", name="The Feed"),
            CafeConfig(slug="side-bar-cafe", name="Side Bar Cafe"),
            CafeConfig(slug="the-sunstream-cafe", name="The Sunstream Cafe"),
            CafeConfig(slug="cadence-cyber-cafe", name="Cadence Cyber Cafe"),
        ),
    ),
}


def get_campus_config(campus_id: str) -> CampusConfig:
    try:
        return CAMPUS_CONFIGS[campus_id]
    except KeyError:
        raise ValueError(
            f"Unknown campus_id: {campus_id!r}. Known campuses: {sorted(CAMPUS_CONFIGS)}"
        ) from None
