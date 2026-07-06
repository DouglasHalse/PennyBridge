#!/usr/bin/env python3
"""Fetch non-Momentum landlords and merge into listings.json"""
import json, re, hashlib, time, requests
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from validate import validate_scraped_listings

all_listings = []

# Load existing
with open('data/listings.json', encoding='utf-8') as f:
    existing = json.load(f)
print(f'Loaded {len(existing["listings"])} existing listings')

# --- PGJ ---
print('\n=== PGJ ===')
try:
    r = requests.get('https://www.pgj.se/wp-json/wp/v2/pages/24', timeout=15)
    r.raise_for_status()
    content = r.json().get('content', {}).get('rendered', '')
    cards = re.findall(r'<a\s+href="([^"]*)"\s+class="apartment"\s+data-place="([^"]*)">(.*?)</a>', content, re.DOTALL)
    count = 0
    for url, place, card_html in cards:
        h2 = re.search(r'<h2>(.*?)</h2>', card_html)
        obj_id = re.search(r'<div class="obj">(.*?)</div>', card_html)
        room_match = re.search(r'<div class="room">\s*(\d+)\s*rok[^,]*,\s*(\d+)\s*kvm', card_html)
        move_in = re.search(r'Inflytt\s+(\d{4}-\d{2}-\d{2})', card_html)
        rent_match = re.search(r'<div class="rent">\s*([\d\s]+)\s*kr/m', card_html)
        img_match = re.search(r'<img[^>]*src="([^"]*)"', card_html)
        addr = h2.group(1).strip() if h2 else ''
        if not addr: continue
        listing = {
            'id': f'pgj_{obj_id.group(1).strip() if obj_id else hashlib.md5(addr.encode()).hexdigest()[:8]}',
            'source': 'pgj', 'displayName': addr, 'address': addr,
            'geocodeQuery': f'{addr}, Örebro, Sweden',
            'type': f'{room_match.group(1)} rum och kök' if room_match else '',
            'shortType': f'{room_match.group(1)} RK' if room_match else '',
            'sqm': float(room_match.group(2)) if room_match else None,
            'price': float(rent_match.group(1).replace(' ', '')) if rent_match else None,
            'availableFrom': move_in.group(1) if move_in else None,
            'image': img_match.group(1) if img_match else None,
            'imageBase': '', 'area': place.strip(), 'areaPath': [place.strip()] if place else [],
            'number': obj_id.group(1).strip() if obj_id else '',
            'url': f'https://www.pgj.se{url}' if url.startswith('/') else url,
            'description': '', 'tags': [],
        }
        all_listings.append(listing)
        count += 1
    print(f'  {count} listings')
    validate_scraped_listings([l for l in all_listings if l["source"] == "pgj"], "pgj", content)
except Exception as e:
    print(f'  ERROR: {e}')

# --- Husherren ---
print('\n=== Husherren ===')
try:
    r = requests.get('https://husherren.realportal.nu/common/portal.php?menuid=109&pageid=117', timeout=20)
    r.encoding = 'iso-8859-1'
    html = r.text
    objects = re.findall(r'class="lediga-object"[^>]*>(.*?)</div>\s*</div>\s*</div>', html, re.DOTALL)
    count = 0
    for obj_html in objects:
        headline = re.search(r'lediga-object-headline[^>]*>(.*?)<', obj_html)
        text_parts = re.findall(r'lediga-object-text[^>]*>(.*?)<', obj_html, re.DOTALL)
        text_clean = [t.strip() for t in text_parts if t.strip()]
        if not headline or len(text_clean) < 4: continue

        # Extract link and image (single quotes in HTML)
        link_match = re.search(r"<a[^>]*href='([^']*)'", obj_html)
        img_match = re.search(r"<img[^>]*src='([^']*)'", obj_html)
        rel_url = link_match.group(1).replace('&amp;', '&') if link_match else ''
        obj_url = 'https://husherren.realportal.nu' + rel_url if rel_url.startswith('/') else rel_url
        img_rel = img_match.group(1).replace('&amp;', '&') if img_match else ''
        img_url = 'https://husherren.realportal.nu' + img_rel if img_rel.startswith('/') else img_rel

        headline_text = headline.group(1).strip()
        parts = [p.strip() for p in headline_text.split('|')]
        addr = parts[0]
        area_name = parts[1] if len(parts) > 1 else ''
        rooms_raw = text_clean[0] if len(text_clean) > 0 else ''
        rm = re.match(r'(\d+)\s*(?:rokv?|Rum och kök)\s*\|\s*(\d+)\s*m', rooms_raw)
        full_addr = text_clean[1] if len(text_clean) > 1 else addr
        post_match = re.search(r'(\d{5})\s+\w+', full_addr)
        postcode = post_match.group(1) if post_match else ''
        rent_raw = text_clean[2].replace('Periodhyra:', '').strip() if len(text_clean) > 2 else ''
        rent_val = float(rent_raw.replace(' ', '').replace(',', '.')) if rent_raw else None
        avail_raw = text_clean[3].replace('Tillgänglig:', '').strip() if len(text_clean) > 3 else None
        # Tags
        tags = []
        combined = f'{addr} {area_name} {rooms_raw}'.lower()
        if 'student' in combined or 'åstadals' in combined:
            tags.append('student')
        listing = {
            'id': f'husherren_{hashlib.md5(addr.encode()).hexdigest()[:8]}',
            'source': 'husherren', 'displayName': addr, 'address': addr,
            'geocodeQuery': f'{addr}, {postcode} Örebro, Sweden' if postcode else f'{addr}, Örebro, Sweden',
            'type': f'{rm.group(1)} rum och kök' if rm else rooms_raw,
            'shortType': f'{rm.group(1)} RK' if rm else '',
            'sqm': float(rm.group(2)) if rm else None,
            'price': rent_val, 'availableFrom': avail_raw,
            'image': img_url if img_url else None, 'imageBase': '',
            'area': area_name, 'areaPath': [area_name] if area_name else [],
            'number': '', 'url': obj_url if obj_url else 'https://husherren.realportal.nu/common/portal.php?menuid=109&pageid=117',
            'description': '', 'tags': tags,
        }
        all_listings.append(listing)
        count += 1
    print(f'  {count} listings')
    validate_scraped_listings([l for l in all_listings if l["source"] == "husherren"], "husherren", html)
except Exception as e:
    print(f'  ERROR: {e}')

# --- Behrn ---
print('\n=== Behrn ===')
try:
    r = requests.get('https://behrn.se/hyresledigt/', timeout=20)
    html = r.text
    section_start = html.find('<div class="objects grid">')
    if section_start < 0:
        print('  No objects grid found')
    else:
        section = html[section_start:section_start + 50000]
        cards = re.split(r'<div class="object" data-type="', section)
        count = 0
        for card in cards[1:]:
            end = card.find('">')
            dtype = card[:end].strip('"')
            body = card[end+2:]
            if dtype != 'bostad': continue
            
            img_match = re.search(r'<img[^>]*src="([^"]*)"', body)
            img = img_match.group(1) if img_match else None
            
            title_match = re.search(r'<div class="object--title">\s*(.*?)\s*</div>', body, re.DOTALL)
            title = title_match.group(1).strip() if title_match else ''
            title = re.sub(r'\([^)]*\)', '', title).strip()
            if not title: continue
            
            link_match = re.search(r'<a href="([^"]*)"', body)
            link = link_match.group(1) if link_match else ''
            
            items = re.findall(r'<li>(?:<span>([^<]*)</span>\s*)?(.*?)</li>', body)
            price = None; rooms = None; sqm = None; available = None
            for label, value in items:
                val = value.strip()
                if 'kr/m' in label or 'kr/m' in val:
                    digits = re.sub(r'[^\d]', '', val)
                    price = float(digits) if digits else None
                elif 'Rum' in label: rooms = val
                elif 'kvm' in val:
                    sqm = float(re.sub(r'[^\d.]', '', val.replace(',', '.')))
                elif 'Tilltrade' in label: available = val
            
            tags = []
            low = title.lower()
            if any(w in low for w in ['student', 'tarnvagen', 'sorbyangsvagen', 'astadalsvagen']):
                tags.append('student')
            
            listing = {
                'id': f'behrn_{hashlib.md5(title.encode()).hexdigest()[:8]}',
                'source': 'behrn', 'displayName': title, 'address': title,
                'geocodeQuery': f'{title}, Orebro, Sweden',
                'type': f'{rooms} rum och kök' if rooms else '',
                'shortType': f'{rooms} RK' if rooms else '',
                'sqm': sqm, 'price': price, 'availableFrom': available,
                'image': img, 'imageBase': '',
                'area': '', 'areaPath': [], 'number': '',
                'url': link, 'description': '', 'tags': tags,
            }
            all_listings.append(listing)
            count += 1
        print(f'  {count} listings')
        validate_scraped_listings([l for l in all_listings if l["source"] == "behrn"], "behrn", html)
except Exception as e:
    print(f'  ERROR: {e}')

# --- Egeryds ---
print('\n=== Egeryds ===')
try:
    r = requests.get('https://egerydsfastigheter.se/wp-json/wp/v2/pages/545', timeout=15)
    r.raise_for_status()
    content = r.json().get('content', {}).get('rendered', '')
    addr_match = re.search(r'<strong>([^<]*gatan[^<]*\d+[^<]*)</strong>', content)
    img_match = re.search(r'<img[^>]*src="([^"]*)"', content)
    if addr_match:
        addr = addr_match.group(1).strip()
        rooms_match = re.search(r'(\d+)\s*rum\s*och\s*kök', content)
        area_match = re.search(r'(\d+)\s*kvm', content)
        rent_match = re.search(r'([\d\s]+)\s*kr/m', content)
        move_match = re.search(r'Inflyttning:\s*(\d{4}-\d{2}-\d{2})', content)
        listing = {
            'id': f'egeryds_{hashlib.md5(addr.encode()).hexdigest()[:8]}',
            'source': 'egeryds', 'displayName': addr, 'address': addr,
            'geocodeQuery': f'{addr}, Örebro, Sweden',
            'type': rooms_match.group(0).strip() if rooms_match else '',
            'shortType': f'{rooms_match.group(1)} RK' if rooms_match else '',
            'sqm': float(area_match.group(1)) if area_match else None,
            'price': float(rent_match.group(1).replace(' ', '')) if rent_match else None,
            'availableFrom': move_match.group(1) if move_match else None,
            'image': img_match.group(1) if img_match and not img_match.group(1).startswith('/') else ('https://egerydsfastigheter.se' + img_match.group(1)) if img_match else None, 'imageBase': '',
            'area': '', 'areaPath': [],
            'number': '', 'url': 'https://egerydsfastigheter.se/lediga-lagenheter/',
            'description': '', 'tags': [],
        }
        all_listings.append(listing)
        print(f'  1 listing: {addr}')
    else:
        print(f'  No address found')
    validate_scraped_listings([l for l in all_listings if l["source"] == "egeryds"], "egeryds", content)
except Exception as e:
    print(f'  ERROR: {e}')

print(f'\n=== Total new: {len(all_listings)} ===')

# --- Geocode new listings ---
print('\n=== Geocoding ===')
try:
    with open('data/geocode-cache.json', encoding='utf-8') as f:
        cache = json.load(f)
except:
    cache = {}

nominatim = Nominatim(user_agent='pennybridge-map')
geocode = RateLimiter(nominatim.geocode, min_delay_seconds=1.1)

geocoded = 0
for i, listing in enumerate(all_listings):
    addr = listing['geocodeQuery'].replace('Orebro', 'Örebro').replace(' ,', ',').strip()
    if addr in cache:
        listing['lat'] = cache[addr].get('lat')
        listing['lon'] = cache[addr].get('lon')
        if listing.get('lat'): geocoded += 1
        continue
    try:
        loc = geocode(addr, timeout=10)
        if loc:
            listing['lat'] = loc.latitude
            listing['lon'] = loc.longitude
            cache[addr] = {'lat': loc.latitude, 'lon': loc.longitude, 'precise': True}
            geocoded += 1
    except:
        pass
    if (i + 1) % 10 == 0:
        print(f'  {geocoded}/{len(all_listings)}')

print(f'  {geocoded}/{len(all_listings)} geocoded')

# --- Merge ---
existing_ids = {l['id'] for l in existing['listings']}
new_only = [l for l in all_listings if l['id'] not in existing_ids]
existing['listings'].extend(new_only)
existing['total'] = len(existing['listings'])
existing['geocoded'] = sum(1 for l in existing['listings'] if l.get('lat'))
existing['notFound'] = existing['total'] - existing['geocoded']

colors = {'obo': '#cf0035', 'ragnfast': '#224b91', 'soderberg': '#862633', 'pgj': '#2e7d32', 'husherren': '#e65100', 'behrn': '#1b232d', 'egeryds': '#6a1b9a'}
names = {'obo': 'Örebrobostäder', 'ragnfast': 'Ragnfast', 'soderberg': 'Söderberg', 'pgj': 'PG Jönsson', 'husherren': 'Husherren', 'behrn': 'Behrn', 'egeryds': 'Egeryds'}
existing['landlords'] = {}
for src in sorted(colors.keys()):
    cnt = sum(1 for l in existing['listings'] if l['source'] == src)
    if cnt > 0:
        existing['landlords'][src] = {'name': names[src], 'color': colors[src], 'count': cnt}

existing['generated'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

with open('data/listings.json', 'w', encoding='utf-8') as f:
    json.dump(existing, f, ensure_ascii=False, indent=2)
with open('data/geocode-cache.json', 'w', encoding='utf-8') as f:
    json.dump(cache, f, ensure_ascii=False, indent=2)

print()
for src in sorted(existing['landlords'].keys()):
    l = existing['landlords'][src]
    gc = sum(1 for x in existing['listings'] if x['source'] == src and x.get('lat'))
    print(f'  {l["name"]:20s}: {l["count"]:3d} listings, {gc} geocoded')
print(f'  {"Total":20s}: {existing["total"]:3d}')
print(f'  Added new: {len(new_only)}, skipped duplicates: {len(all_listings) - len(new_only)}')
