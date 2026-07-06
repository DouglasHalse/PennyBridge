#!/usr/bin/env python3
"""
PennyBridge scraper validation module.
Import and use validate_scraped_listings() after each scraper run.
"""

import json
import re
import os
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
SNAPSHOTS_DIR = DATA_DIR / "snapshots"

# Minimum expected counts per landlord (updated after each healthy run)
MIN_EXPECTED = {
    "pgj": 10,
    "husherren": 30,
    "behrn": 15,
    "egeryds": 0,  # Often has 0-1 listings, don't enforce minimum
}


def validate_listing(listing, source):
    """Validate a single listing. Returns list of error strings (empty = valid)."""
    errors = []

    # Required fields must be non-empty
    if not listing.get("displayName") or not listing.get("displayName").strip():
        errors.append("missing displayName")
    if not listing.get("address") or not listing.get("address").strip():
        errors.append("missing address")

    # Address must look like a Swedish street address (contains a number)
    addr = listing.get("address", "")
    if addr and not re.search(r"\d", addr):
        errors.append(f"address has no street number: '{addr}'")

    # Price must be a positive number
    price = listing.get("price")
    if price is not None:
        if not isinstance(price, (int, float)):
            errors.append(f"price is not numeric: {type(price).__name__} = {price}")
        elif price <= 0:
            errors.append(f"price is zero or negative: {price}")
        elif price > 50000:
            errors.append(f"price suspiciously high: {price}")

    # sqm must be reasonable
    sqm = listing.get("sqm")
    if sqm is not None:
        if not isinstance(sqm, (int, float)):
            errors.append(f"sqm is not numeric: {type(sqm).__name__} = {sqm}")
        elif sqm < 8 or sqm > 500:
            errors.append(f"sqm out of range: {sqm}")

    # type/rooms should have some content for apartments
    if source != "behrn":  # Behrn sometimes has empty type for group listings
        if not listing.get("type") or not listing.get("type").strip():
            errors.append("missing type/rooms")

    # Check for HTML artifacts (scraper captured raw HTML instead of text)
    for field in ["displayName", "address", "type"]:
        val = listing.get(field, "")
        if val and ("<" in val or ">" in val):
            errors.append(f"{field} contains HTML tags: '{val[:80]}'")

    return errors


def validate_scraped_listings(listings, source, raw_html=None):
    """
    Validate a batch of scraped listings. Prints a report and raises
    RuntimeError if validation is critically broken.

    Args:
        listings: list of normalized listing dicts
        source: landlord key (e.g. 'pgj', 'husherren')
        raw_html: optional raw HTML string for snapshot on failure
    """
    source_name = source.upper() if source == "pgj" else source.capitalize()
    print(f"\n  [{source}] Validating {len(listings)} listings...")

    # --- Check 1: Count sanity ---
    min_expected = MIN_EXPECTED.get(source, 0)
    if len(listings) < min_expected:
        msg = f"  [{source}] WARNING: Got {len(listings)} listings, expected at least {min_expected}."
        if len(listings) == 0:
            msg += " SCRAPER MAY BE BROKEN."
        print(msg)

        # Save snapshot for debugging
        if raw_html and len(listings) == 0:
            save_snapshot(source, raw_html)

        if min_expected > 0 and len(listings) == 0:
            raise RuntimeError(
                f"[{source}] Scraper returned 0 listings (expected >= {min_expected}). "
                f"Site may have changed structure. Snapshot saved to {SNAPSHOTS_DIR}"
            )

    # --- Check 2: Per-listing validation ---
    error_count = 0
    sample_errors = []
    for listing in listings:
        errors = validate_listing(listing, source)
        if errors:
            error_count += 1
            if len(sample_errors) < 5:
                sample_errors.append((listing.get("displayName", "?"), errors))

    if error_count > 0:
        error_pct = 100 * error_count / len(listings)
        print(f"  [{source}] {error_count}/{len(listings)} listings have validation errors ({error_pct:.0f}%)")
        for name, errs in sample_errors:
            print(f"    {name}: {', '.join(errs)}")

        if error_pct > 50:
            raise RuntimeError(
                f"[{source}] Over 50% of listings ({error_pct:.0f}%) failed validation. "
                f"Scraper likely broken."
            )
    else:
        print(f"  [{source}] All {len(listings)} listings passed validation")

    # --- Check 3: Duplicate detection ---
    addrs = [l.get("address", "") for l in listings]
    dupes = [a for a in addrs if addrs.count(a) > 1]
    unique_dupes = set(dupes)
    if unique_dupes:
        print(f"  [{source}] {len(dupes)} duplicate addresses ({len(unique_dupes)} unique)")
        # Duplicates are OK (same building, different units) but worth logging

    return True


def save_snapshot(source, html):
    """Save raw HTML for debugging when a scraper breaks."""
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = SNAPSHOTS_DIR / f"{source}_{ts}.html"
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path


def update_expected_counts(listings_by_source):
    """After a successful run, update MIN_EXPECTED for next time."""
    # Read current values
    config_path = __file__
    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()

    updated = False
    for source, listings in listings_by_source.items():
        if source not in MIN_EXPECTED:
            continue
        current_min = MIN_EXPECTED[source]
        new_count = len(listings)
        # Set new min to 50% of current count (rounded down, min 1)
        new_min = max(1, new_count // 2)
        if new_min != current_min and new_min > 0:
            old_line = f'    "{source}": {current_min},'
            new_line = f'    "{source}": {new_min},'
            content = content.replace(old_line, new_line)
            updated = True
            print(f"  Updated MIN_EXPECTED[{source}]: {current_min} -> {new_min}")

    if updated:
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(content)
        print("  MIN_EXPECTED updated in validate.py")
