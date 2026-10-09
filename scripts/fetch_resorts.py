"""Builds service/app/data/resorts.json from OpenStreetMap (one-time / occasional refresh).

Data (c) OpenStreetMap contributors, ODbL. Run from the repo root:
    python scripts/fetch_resorts.py
"""
import json
import re
import sys
import time
import unicodedata
from pathlib import Path

import requests

ENDPOINTS = [
    'https://overpass-api.de/api/interpreter',
    'https://overpass.kumi.systems/api/interpreter',
    'https://overpass.private.coffee/api/interpreter',
]
HEADERS = {'User-Agent': 'SlopeAPI-seed/1.0 (https://github.com/samblake00/slope-api)'}

# south, west, north, east
REGIONS = {
    'north-america-west': (24, -170, 72, -100),
    'north-america-east': (24, -100, 72, -50),
    'south-america': (-60, -90, 14, -30),
    'europe-west': (34, -25, 72, 10),
    'europe-east': (34, 10, 72, 45),
    'asia-north': (36, 45, 78, 180),
    'asia-south': (-12, 45, 36, 180),
    'oceania': (-50, 105, -8, 180),
    'africa': (-36, -20, 36, 55),
}

QUERY = '[out:json][timeout:240][bbox:{s},{w},{n},{e}];(nwr["landuse"="winter_sports"]["name"];);out center tags;'


def fetch_region(bbox, depth=0):
    s, w, n, e = bbox
    query = QUERY.format(s=s, w=w, n=n, e=e)
    last = None
    for attempt in range(4):
        url = ENDPOINTS[attempt % len(ENDPOINTS)]
        try:
            r = requests.post(url, data={'data': query}, headers=HEADERS, timeout=300)
            if r.status_code == 200:
                return r.json()['elements']
            last = f'{url} -> {r.status_code}'
        except (requests.RequestException, ValueError) as exc:
            last = f'{url} -> {exc}'
        time.sleep(10 * (attempt + 1))
    if depth >= 2:
        print(f'  giving up on {bbox}: {last}', flush=True)
        return []
    # Smaller areas are cheaper for Overpass; retry as four quadrants
    ms, mw = (s + n) / 2, (w + e) / 2
    parts = [(s, w, ms, mw), (s, mw, ms, e), (ms, w, n, mw), (ms, mw, n, e)]
    print(f'  splitting {bbox} after: {last}', flush=True)
    return [el for p in parts for el in fetch_region(p, depth + 1)]


def slugify(text):
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


def main():
    resorts = {}
    for name, bbox in REGIONS.items():
        elements = fetch_region(bbox)
        print(f'{name}: {len(elements)} elements', flush=True)
        for el in elements:
            tags = el.get('tags', {})
            lat = el.get('lat') or (el.get('center') or {}).get('lat')
            lng = el.get('lon') or (el.get('center') or {}).get('lon')
            if not tags.get('name') or lat is None or lng is None:
                continue
            ext_id = f"osm-{el['type'][0]}{el['id']}"
            website = tags.get('website') or tags.get('contact:website') or None
            if website and not website.startswith(('http://', 'https://')):
                website = 'https://' + website
            resorts[ext_id] = {
                'external_id': ext_id,
                'name': tags['name'][:255],
                'location': ', '.join(
                    p for p in (tags.get('addr:city'), tags.get('addr:state'), tags.get('addr:country')) if p
                ) or None,
                'lat': round(lat, 5),
                'lng': round(lng, 5),
                'website': website[:255] if website else None,
            }
        time.sleep(5)

    # Large areas are often split into many OSM polygons; keep one entry per name within ~25 km
    kept, seen = [], {}
    for r in sorted(resorts.values(), key=lambda r: (r['website'] is None, r['external_id'])):
        key = slugify(r['name'])
        if any(abs(r['lat'] - o['lat']) < 0.25 and abs(r['lng'] - o['lng']) < 0.25 for o in seen.get(key, [])):
            continue
        seen.setdefault(key, []).append(r)
        kept.append(r)

    kept.sort(key=lambda r: (r['name'].lower(), r['external_id']))
    out = Path(__file__).resolve().parent.parent / 'service' / 'app' / 'data' / 'resorts.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(kept, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    print(f'wrote {len(kept)} resorts ({len(resorts)} before de-duplication) -> {out}')


if __name__ == '__main__':
    sys.exit(main())
