#!/usr/bin/env python3
"""
PennyBridge — Multi-landlord rental listing aggregator for Orebro.
Fetches from Momentum APIs (OBO, Ragnfast, Soderberg) + WP/HTML scraping.
Outputs combined JSON for the frontend map.
"""

import json
import os
import re
import time
import hashlib
from pathlib import Path
from urllib.parse import urlencode

import requests
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

# --- Config ---
API_KEY = "pJnKrR6B3FzRNFsF33xL8LhSs55KPJrm"
GEOAPIFY_KEY = "b6f995767b844f73871eb632ebee3d12"
GOOGLE_KEY = os.environ.get("GOOGLE_GEOCODE_KEY", "")

OUTPUT = Path(__file__).parent.parent / "data" / "listings.json"
GEOCODE_CACHE = Path(__file__).parent.parent / "data" / "geocode-cache.json"

HEADERS = {"X-Api-Key": API_KEY, "Accept": "application/json"}
LIMIT = 100

# --- Landlord config ---
LANDLORD_COLORS = {
    "obo":       "#cf0035",
    "ragnfast":  "#224b91",
    "soderberg": "#862633",
    "pgj":       "#2e7d32",
    "husherren": "#e65100",
    "behrn":     "#1b232d",
    "egeryds":   "#6a1b9a",
}

LANDLORD_NAMES = {
    "obo":       "Örebrobostäder",
    "ragnfast":  "Ragnfast",
    "soderberg": "Söderberg",
    "pgj":       "PG Jönsson",
    "husherren": "Husherren",
    "behrn":     "Behrn",
    "egeryds":   "Egeryds",
    "heimstaden":"Heimstaden",
}

MOMENTUM_SOURCES = {
    "obo": {
        "api": "https://obo-fastighet.momentum.se/Prod/Obo/PmApi/v2/market/objects",
        "types": {
            "residential":               "Bostad",
            "VJKbFxvkM99GGWCvwXyhWYCX": "Bostad Snabbvalet",
            "X7PPpCMvT7FHDfGVJgBtytKc":  "Seniorbostad",
            "BwCRpdHRgKvKXprdYwptKVKg":  "Studentbostad",
            "qppm9gc6c96FHHvjWbTQbd8J":  "Ungdomsbostad",
        },
        "city": "Orebro",
    },
    "ragnfast": {
        "api": "https://ragnfast-fastighet.momentum.se/Prod/Ragnfast/PmApi/v2/market/objects",
        "types": {"residential": "Bostad"},
        "city": "Orebro",
    },
    "soderberg": {
        "api": "https://soderberg-fastighet.momentum.se/Prod/Soderberg/PmApi/v2/market/objects",
        "types": {"residential": "Bostad"},
        "city": "Orebro",
    },
}

ADDRESS_FIXES = {
    "L Wivallius vag":   "Lars Wivallius vag",
    "Hj Bergmans Vag":   "Hjalmar Bergmans vag",
    "Hj Bergmans vag":   "Hjalmar Bergmans vag",
    "O Vintergatan":     "Ostra Vintergatan",
}


def parse_date(ms_str):
    if not ms_str:
        return None
    try:
        ms = int(ms_str.strip("/Date()"))
        from datetime import datetime, timezone
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def fetch_momentum(source_id, config):
    """Fetch all residential listings from a Momentum API source."""
    items = []
    for type_id, type_label in config["types"].items():
        print(f"  [{source_id}] type={type_id} ({type_label})")
        params = {"type": type_id, "limit": LIMIT, "offset": 0}
        resp = requests.get(f"{config['api']}?{urlencode(params)}", headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        total = data["count"]
        for item in data["items"]:
            item["_source"] = source_id
            item["_type_id"] = type_id
            item["_type_label"] = type_label
        items.extend(data["items"])
        for offset in range(LIMIT, total, LIMIT):
            params["offset"] = offset
            resp = requests.get(f"{config['api']}?{urlencode(params)}", headers=HEADERS, timeout=30)
            resp.raise_for_status()
            page = resp.json()
            for item in page["items"]:
                item["_source"] = source_id
                item["_type_id"] = type_id
                item["_type_label"] = type_label
            items.extend(page["items"])
        print(f"    {total} items")
    return items


def normalize_momentum(item, config):
    """Normalize a Momentum API item into the common schema."""
    loc = item.get("location", {})
    size = item.get("size", {})
    display_name = item.get("displayName", "")

    # Determine city: use areaPath[0] only if it looks like a city (not a district)
    area_path = [a.get("displayName", "") for a in loc.get("areaPath", [])]
    first_area = area_path[0] if area_path else ""
    # Known cities outside Örebro that appear in areaPath
    non_orebro_cities = {"nora", "kumla", "lindesberg", "karlskoga", "eskilstuna"}
    if first_area.lower() in non_orebro_cities:
        city = first_area
    else:
        city = config["city"]

    # Build geocode query
    street = display_name.strip()
    geocode_query = f"{street}, {city}, Sweden"

    # Apply address fixes
    for short, full in ADDRESS_FIXES.items():
        if short.lower() in geocode_query.lower():
            geocode_query = geocode_query.replace(short, full)

    return {
        "id": f"{item['_source']}_{item['id']}",
        "source": item["_source"],
        "displayName": display_name,
        "address": street,
        "geocodeQuery": geocode_query,
        "type": size.get("roomsDisplayName", ""),
        "shortType": size.get("shortRoomsDisplayName", ""),
        "sqm": size.get("area"),
        "price": item.get("pricing", {}).get("price"),
        "availableFrom": parse_date(item.get("availability", {}).get("availableFrom")),
        "image": item.get("thumbnail", {}).get("exists") and item["id"] or None,
        "imageBase": config["api"].replace("/v2/market/objects", ""),
        "area": item.get("location", {}).get("area", {}).get("displayName", ""),
        "areaPath": area_path,
        "number": item.get("number", ""),
        "signNumber": (loc.get("signNumber") or "").strip(),
        "description": item.get("description", ""),
        "url": f"https://minasidor.{item['_source']}.se/market/{item['_type_id']}/{item['id']}",
        "tags": detect_tags(item),
    }


def fetch_pgj():
    """Fetch PGJ listings from WordPress REST API."""
    print("  [pgj] Fetching from WordPress REST API...")
    items = []
    try:
        resp = requests.get("https://www.pgj.se/wp-json/wp/v2/pages/24", timeout=15)
        resp.raise_for_status()
        data = resp.json()
        content = data.get("content", {}).get("rendered", "")

        # Parse apartment cards from HTML
        cards = re.findall(r'<a\s+href="([^"]*)"\s+class="apartment"\s+data-place="([^"]*)">(.*?)</a>', content, re.DOTALL)
        for url, place, card_html in cards:
            h2 = re.search(r'<h2>(.*?)</h2>', card_html)
            obj_id = re.search(r'<div class="obj">(.*?)</div>', card_html)
            room = re.search(r'<div class="room">\s*(.*?)\s*</div>', card_html)
            desc = re.search(r'<div class="description">\s*(.*?)\s*</div>', card_html, re.DOTALL)
            move_in = re.search(r'<div class="move-in">\s*Inflytt\s+(.*?)\s*</div>', card_html)
            rent = re.search(r'<div class="rent">\s*(.*?)\s*kr/m', card_html)
            img = re.search(r'<img[^>]*src="([^"]*)"', card_html)

            address = h2.group(1).strip() if h2 else ""
            rooms_raw = room.group(1).strip() if room else ""
            # Parse "3 rok, 84 kvm" -> rooms="3", sqm=84
            rooms_match = re.match(r'(\d+)\s*rok[^,]*,\s*(\d+)\s*kvm', rooms_raw)
            rooms_num = int(rooms_match.group(1)) if rooms_match else None
            sqm = float(rooms_match.group(2)) if rooms_match else None

            items.append({
                "id": f"pgj_{obj_id.group(1).strip() if obj_id else hashlib.md5(address.encode()).hexdigest()[:8]}",
                "source": "pgj",
                "displayName": address,
                "address": address,
                "geocodeQuery": f"{address}, Orebro, Sweden",
                "type": f"{rooms_num} rum och kök" if rooms_num else rooms_raw,
                "shortType": f"{rooms_num} RK" if rooms_num else rooms_raw,
                "sqm": sqm,
                "price": float(rent.group(1).replace(" ", "")) if rent else None,
                "availableFrom": move_in.group(1).strip() if move_in else None,
                "image": img.group(1) if img else None,
                "imageBase": "",
                "area": place.strip() if place else "",
                "areaPath": [place.strip()] if place else [],
                "number": obj_id.group(1).strip() if obj_id else "",
                "url": f"https://www.pgj.se{url}" if url.startswith("/") else url,
                "description": desc.group(1).strip()[:300] if desc else "",
                "tags": [],
            })
        print(f"    {len(items)} items")
    except Exception as e:
        print(f"    ERROR: {e}")
    return items


def fetch_husherren():
    """Fetch Husherren listings from HTML scraping."""
    print("  [husherren] Scraping Realportal HTML...")
    items = []
    try:
        resp = requests.get("https://husherren.realportal.nu/common/portal.php?menuid=109&pageid=117", timeout=20)
        resp.encoding = "iso-8859-1"
        html = resp.text

        objects = re.findall(r'class="lediga-object"[^>]*>(.*?)</div>\s*</div>\s*</div>', html, re.DOTALL)
        for obj_html in objects:
            headline = re.search(r'lediga-object-headline[^>]*>(.*?)<', obj_html)
            text_parts = re.findall(r'lediga-object-text[^>]*>(.*?)<', obj_html, re.DOTALL)
            text_clean = [t.strip() for t in text_parts if t.strip()]

            if not headline or len(text_clean) < 4:
                continue

            # Headline: "Langbrotorg 1 | Norr"
            headline_text = headline.group(1).strip()
            parts = [p.strip() for p in headline_text.split("|")]
            address = parts[0]
            area_name = parts[1] if len(parts) > 1 else ""

            # text_clean[0]: "1 rok | 47 m²"
            # text_clean[1]: "Langbrotorg 1, 70366 Orebro"
            # text_clean[2]: "Periodhyra: 6 445,90"
            # text_clean[3]: "Tillganglig: 2026-09-01"

            rooms_raw = text_clean[0] if len(text_clean) > 0 else ""
            rooms_match = re.match(r'(\d+)\s*(?:rokv?|Rum och kok)\s*\|\s*(\d+)\s*m', rooms_raw)
            rooms_num = int(rooms_match.group(1)) if rooms_match else None
            sqm = float(rooms_match.group(2)) if rooms_match else None

            full_addr = text_clean[1] if len(text_clean) > 1 else address
            # Extract postcode + city: "70366 Örebro" or "63219 Eskilstuna"
            post_match = re.search(r'(\d{5})\s+(\w+)', full_addr)
            if post_match:
                postcode = post_match.group(1)
                city_from_addr = post_match.group(2)
                geocode_query = f"{address}, {postcode} {city_from_addr}, Sweden"
            else:
                geocode_query = f"{address}, Örebro, Sweden"

            rent_raw = text_clean[2].replace("Periodhyra:", "").strip() if len(text_clean) > 2 else ""
            rent_val = float(rent_raw.replace(" ", "").replace(",", ".")) if rent_raw else None

            avail_raw = text_clean[3].replace("Tillgänglig:", "").replace("Tillganglig:", "").strip() if len(text_clean) > 3 else None

            items.append({
                "id": f"husherren_{hashlib.md5(address.encode()).hexdigest()[:8]}",
                "source": "husherren",
                "displayName": address,
                "address": address,
                "geocodeQuery": geocode_query,
                "type": f"{rooms_num} rum och kök" if rooms_num else rooms_raw,
                "shortType": f"{rooms_num} RK" if rooms_num else "",
                "sqm": sqm,
                "price": rent_val,
                "availableFrom": avail_raw,
                "image": _extract_husherren_image(obj_html),
                "imageBase": "",
                "area": area_name,
                "areaPath": [area_name] if area_name else [],
                "number": "",
                "url": _extract_husherren_url(obj_html),
                "description": "",
                "tags": detect_tags_husherren(address, area_name, rooms_raw),
            })
        print(f"    {len(items)} items")
    except Exception as e:
        print(f"    ERROR: {e}")
    return items


def fetch_behrn():
    """Fetch Behrn listings — scrape the hyresledigt listing page only."""
    print("  [behrn] Scraping listing page...")
    items = []
    try:
        resp = requests.get("https://behrn.se/hyresledigt/", timeout=20)
        html = resp.text

        # Find listing cards with data-type attributes
        # Pattern: each listing card has address as heading, with data-type="bostad"
        # The listings are rendered as HTML but may be dynamically loaded.
        # Try to find any embedded JSON or structured listings
        cards = re.findall(r'<div[^>]*class="[^"]*object[^"]*"[^>]*>(.*?)</article>', html, re.DOTALL)
        if not cards:
            cards = re.findall(r'<article[^>]*>(.*?)</article>', html, re.DOTALL)

        # Alternative: find all heading+link combinations
        objects = re.findall(r'<a[^>]*href="(/objekt/[^"]*)"[^>]*>(.*?)</a>', html)
        seen = set()
        for slug, text in objects:
            if slug in seen:
                continue
            seen.add(slug)
            title = re.sub(r'<[^>]+>', '', text).strip()
            if not title or len(title) < 3:
                continue

            items.append({
                "id": f"behrn_{hashlib.md5(slug.encode()).hexdigest()[:8]}",
                "source": "behrn",
                "displayName": title,
                "address": title,
                "geocodeQuery": f"{title}, Orebro, Sweden",
                "type": "",
                "shortType": "",
                "sqm": None,
                "price": None,
                "availableFrom": None,
                "image": None,
                "imageBase": "",
                "area": "",
                "areaPath": [],
                "number": "",
                "url": f"https://behrn.se{slug}",
                "description": "",
                "tags": [],
            })
        print(f"    {len(items)} items (addresses only, no detail scraping)")
    except Exception as e:
        print(f"    ERROR: {e}")
    return items


def fetch_egeryds():
    """Fetch Egeryds listing from WordPress REST API."""
    print("  [egeryds] Fetching from WP REST API...")
    items = []
    try:
        resp = requests.get("https://egerydsfastigheter.se/wp-json/wp/v2/pages/545", timeout=15)
        resp.raise_for_status()
        data = resp.json()
        content = data.get("content", {}).get("rendered", "")

        # Find address patterns
        addr_match = re.search(r'<strong>([^<]*gatan[^<]*\d+[^<]*)</strong>', content)
        if addr_match:
            address = addr_match.group(1).strip()
            # Find rooms
            rooms_match = re.search(r'(\d+)\s*rum\s*och\s*kok', content)
            # Find sqm
            area_match = re.search(r'(\d+)\s*kvm', content)
            # Find rent
            rent_match = re.search(r'(\d[\d\s]*)\s*kr/m', content)
            # Find move-in
            move_match = re.search(r'Inflyttning:\s*(\d{4}-\d{2}-\d{2})', content)
            img_match = re.search(r'<img[^>]*src="([^"]*wp-content[^"]*)"', content)

            items.append({
                "id": f"egeryds_{hashlib.md5(address.encode()).hexdigest()[:8]}",
                "source": "egeryds",
                "displayName": address,
                "address": address,
                "geocodeQuery": f"{address}, Orebro, Sweden",
                "type": rooms_match.group(0).strip() if rooms_match else "",
                "shortType": f"{rooms_match.group(1)} RK" if rooms_match else "",
                "sqm": float(area_match.group(1)) if area_match else None,
                "price": float(rent_match.group(1).replace(" ", "")) if rent_match else None,
                "availableFrom": move_match.group(1) if move_match else None,
                "image": _fix_relative_url(img_match.group(1), "egerydsfastigheter.se") if img_match else None,
                "imageBase": "",
                "area": "",
                "areaPath": [],
                "number": "",
                "url": "https://egerydsfastigheter.se/lediga-lagenheter/",
                "description": "",
                "tags": [],
            })
        print(f"    {len(items)} items")
    except Exception as e:
        print(f"    ERROR: {e}")
    return items


def detect_tags(item):
    """Detect cross-landlord tags from Momentum item data."""
    tags = []
    type_id = item.get("_type_id", "")
    display_name = item.get("displayName", "").lower()
    description = item.get("description", "").lower()

    # OBO-specific type tags
    if type_id == "BwCRpdHRgKvKXprdYwptKVKg":
        tags.append("student")
    if type_id == "X7PPpCMvT7FHDfGVJgBtytKc":
        tags.append("senior")
    if type_id == "qppm9gc6c96FHHvjWbTQbd8J":
        tags.append("youth")
    if type_id == "VJKbFxvkM99GGWCvwXyhWYCX":
        tags.append("quick-pick")

    return tags


def detect_tags_husherren(address, area, rooms):
    """Detect tags from Husherren listing data."""
    tags = []
    combined = f"{address} {area} {rooms}".lower()
    if "student" in combined or "astadalsvagen" in combined:
        tags.append("student")
    if "senior" in combined:
        tags.append("senior")
    if "ungdom" in combined:
        tags.append("youth")
    return tags


def _extract_husherren_url(obj_html):
    """Extract individual object URL from Husherren card HTML (single-quoted href)."""
    BASE = "https://husherren.realportal.nu"
    link_match = re.search(r"<a[^>]*href='([^']*)'", obj_html)
    if link_match:
        rel_url = link_match.group(1).replace("&amp;", "&")
        return BASE + rel_url if rel_url.startswith("/") else rel_url
    return f"{BASE}/common/portal.php?menuid=109&pageid=117"


def _extract_husherren_image(obj_html):
    """Extract image URL from Husherren card HTML (single-quoted src)."""
    BASE = "https://husherren.realportal.nu"
    img_match = re.search(r"<img[^>]*src='([^']*)'", obj_html)
    if img_match:
        rel_url = img_match.group(1).replace("&amp;", "&")
        return BASE + rel_url if rel_url.startswith("/") else rel_url
    return None


def _fix_relative_url(url, domain):
    """Prepend https://domain to relative URLs."""
    if url and url.startswith("/"):
        return f"https://{domain}{url}"
    return url


def geocode_addresses(spots):
    """Geocode addresses using Google > Geoapify > Nominatim fallback chain."""
    cache = {}
    if GEOCODE_CACHE.exists():
        with open(GEOCODE_CACHE, encoding="utf-8") as f:
            cache = json.load(f)
        print(f"Loaded {len(cache)} cached geocode results")

    nominatim = Nominatim(user_agent="pennybridge-map")
    nom_geocode = RateLimiter(nominatim.geocode, min_delay_seconds=1.1)

    # Find unique addresses not in cache
    unique = {}
    for spot in spots:
        addr = spot["geocodeQuery"]
        if addr not in unique:
            unique[addr] = []

    to_geocode = [a for a in unique if a not in cache]
    to_retry = [a for a in unique if a in cache and not cache[a].get("precise") and cache[a].get("lat")]

    print(f"New addresses: {len(to_geocode)}, retrying imprecise: {len(to_retry)}")

    all_to_geocode = to_geocode + to_retry
    for i, addr in enumerate(all_to_geocode):
        result = None
        if GOOGLE_KEY:
            result = _geocode_google(addr)
        if not result:
            result = _geocode_geoapify(addr)
        if not result:
            result = _geocode_nominatim(addr, nom_geocode)

        if result:
            lat, lon, precise = result
            cache[addr] = {"lat": lat, "lon": lon, "precise": precise}
        else:
            cache[addr] = {"lat": None, "lon": None, "precise": False}
            print(f"  [{i+1}] NOT FOUND: {addr}")

        if (i + 1) % 20 == 0:
            with open(GEOCODE_CACHE, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)
            print(f"  Saved cache ({len(cache)} entries)")
        time.sleep(0.15)

    with open(GEOCODE_CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

    for spot in spots:
        addr = spot["geocodeQuery"]
        coords = cache.get(addr, {})
        spot["lat"] = coords.get("lat")
        spot["lon"] = coords.get("lon")
        spot["precise"] = coords.get("precise", False)

    precise = sum(1 for s in spots if s.get("precise"))
    geocoded = sum(1 for s in spots if s["lat"])
    print(f"  Geocoded: {geocoded}/{len(spots)}, precise: {precise} ({100*precise//max(len(spots),1)}%)")
    return spots


def _geocode_google(addr):
    try:
        r = requests.get("https://maps.googleapis.com/maps/api/geocode/json", params={
            "address": addr, "key": GOOGLE_KEY
        }, timeout=10)
        r.raise_for_status()
        data = r.json()
        if data["status"] == "OK":
            res = data["results"][0]
            loc = res["geometry"]["location"]
            precise = res.get("geometry", {}).get("location_type") == "ROOFTOP"
            return (loc["lat"], loc["lng"], precise)
    except Exception as e:
        print(f"    Google error: {e}")
    return None


def _geocode_geoapify(addr):
    try:
        r = requests.get("https://api.geoapify.com/v1/geocode/search", params={
            "text": addr, "format": "json", "apiKey": GEOAPIFY_KEY, "limit": 1
        }, timeout=10)
        r.raise_for_status()
        results = r.json().get("results", [])
        if results:
            res = results[0]
            precise = res.get("result_type") == "building"
            return (res["lat"], res["lon"], precise)
    except Exception as e:
        print(f"    Geoapify error: {e}")
    return None


def _geocode_nominatim(addr, geocode_fn):
    try:
        loc = geocode_fn(addr, addressdetails=True)
        if loc:
            cls = loc.raw.get("class", "")
            return (loc.latitude, loc.longitude, cls not in ("highway",))
    except Exception:
        pass
    return None


def main():
    print("=== PennyBridge — Multi-Landlord Data Pipeline ===\n")

    all_spots = []

    # Tier 1: Momentum APIs
    print("--- Momentum APIs ---")
    for source_id, config in MOMENTUM_SOURCES.items():
        items = fetch_momentum(source_id, config)
        spots = [normalize_momentum(item, config) for item in items]
        all_spots.extend(spots)
        print(f"  Total {source_id}: {len(spots)} normalized\n")

    # Tier 2: WordPress REST API
    print("--- WordPress / HTML Scraping ---")
    all_spots.extend(fetch_pgj())
    all_spots.extend(fetch_husherren())

    # Tier 3: Per-item scraping (slowest, do last)
    all_spots.extend(fetch_behrn())
    all_spots.extend(fetch_egeryds())

    print(f"\n=== Total raw listings: {len(all_spots)} ===\n")

    # Filter: apartments only (residential), drop items without addresses
    apartments = [s for s in all_spots if s["address"] and s["source"] != "unknown"]
    # Drop non-residential from Momentum (parking, commercial, etc.)
    # We only fetch residential types, but double-check
    print(f"Residential apartments: {len(apartments)}")

    # Geocode
    print("\n=== Geocoding ===\n")
    apartments = geocode_addresses(apartments)

    # Output
    geocoded = sum(1 for s in apartments if s["lat"])
    not_found = sum(1 for s in apartments if not s["lat"])

    print(f"\n=== Writing: {OUTPUT} ===\n")
    output = {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total": len(apartments),
        "geocoded": geocoded,
        "notFound": not_found,
        "listings": apartments,
        "landlords": {
            lid: {
                "name": LANDLORD_NAMES.get(lid, lid.capitalize()),
                "color": LANDLORD_COLORS.get(lid, "#888"),
                "count": sum(1 for s in apartments if s["source"] == lid),
            }
            for lid in sorted(LANDLORD_COLORS.keys())
        },
    }
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"Done! {geocoded} geocoded, {not_found} not found ({OUTPUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
