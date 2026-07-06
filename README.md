# PennyBridge

Rental map for Örebro -- see available apartments from 8 landlords on one map.

**Live at:** [douglashalse.github.io/PennyBridge](https://douglashalse.github.io/PennyBridge)

## Landlords

| Landlord | Listings | Source |
|----------|----------|--------|
| Örebrobostäder | 146 | Momentum API |
| Husherren | 51 | HTML scraping |
| Behrn Fastigheter | 28 | HTML scraping |
| Ragnfast | 25 | Momentum API |
| PG Jönsson | 22 | WP REST API |
| Söderberg | 11 | Momentum API |
| Heimstaden | 3 | HTML scraping |
| Egeryds | 1 | WP REST API |

## How it works

A Python pipeline fetches listings from each landlord daily via GitHub Actions, normalizes them into a common schema, geocodes addresses, and outputs a single JSON file. The frontend is a static HTML page with Leaflet maps.

- **Momentum landlords** (ÖBO, Ragnfast, Söderberg) share the same platform and API key
- **WordPress landlords** (PG Jönsson, Behrn, Egeryds) are scraped from their public listing pages
- **PHP landlords** (Husherren) use HTML parsing
- **Heimstaden** uses WordPress with structured listing cards

## Local development

```bash
# Fetch data
python scripts/fetch_listings.py
python scripts/fetch_extra.py

# Serve locally
python -m http.server 8080 --bind 0.0.0.0
# Open http://localhost:8080
```

## Tech

Leaflet, MarkerCluster, static GitHub Pages site, Python data pipeline, daily cron via GitHub Actions. This project is almost entirely AI-generated.
