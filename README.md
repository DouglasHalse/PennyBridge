# PennyBridge

Rental map for Örebro -- see available apartments from 9 landlords on one map.

**Live at:** [douglashalse.github.io/PennyBridge](https://douglashalse.github.io/PennyBridge)

## Landlords

| Landlord | Source | Method |
|----------|--------|--------|
| Örebrobostäder (ÖBO) | obo.se | Momentum API |
| Ragnfast | ragnfast.se | Momentum API |
| Söderberg | soderberg.se | Momentum API |
| PG Jönsson | pgj.se | WordPress REST API |
| Husherren | husherren.realportal.nu | HTML scraping |
| Behrn | behrn.se | HTML scraping + detail pages |
| Egeryds | egerydsfastigheter.se | WordPress REST API |
| Heimstaden | heimstaden.com | HTML scraping |
| HomeQ | homeq.se | Public REST API (19 landlords) |

## How it works

A Python pipeline fetches listings from each landlord daily via GitHub Actions, normalizes them into a common schema, geocodes addresses with Google Maps, and outputs a single JSON file. The frontend is a static HTML page with Leaflet maps.

- **Momentum landlords** -- ÖBO, Ragnfast, Söderberg share the same platform and API key
- **WordPress landlords** -- PG Jönsson, Egeryds scraped from public listing pages
- **HTML scraping** -- Husherren, Behrn, Heimstaden parsed from server-rendered HTML
- **HomeQ API** -- 19 landlords aggregated via public card search endpoint

## Features

- Per-landlord color-coded markers with clustering
- Landlord tabs, room count slider, max price slider
- Tag pills: student, senior, youth, quick-pick
- Language toggle: SV / EN
- One-click location report (sends to GitHub Issues)
- Location editor at `/editor.html` for manual coordinate fixes

## Local development

```bash
pip install requests geopy

# Fetch data
python scripts/fetch_listings.py
python scripts/fetch_extra.py

# Serve locally
python -m http.server 8080 --bind 0.0.0.0
# Open http://127.0.0.1:8080
```

## Tech

Leaflet, MarkerCluster, static GitHub Pages, Python data pipeline, daily cron via GitHub Actions, Google Geocoding API. Location reports via custom PHP endpoint on douglashalse.com.

This project was almost entirely vibe-coded with Hermes Agent.
