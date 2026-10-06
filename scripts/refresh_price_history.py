"""Fetch bounded, public LuxPrice chart series. Never request gated result pages.
Run from repository root: .venv/bin/python scripts/refresh_price_history.py
"""
import argparse
import hashlib
import json
import math
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

import requests
from bs4 import BeautifulSoup

BASE = 'https://www.collectorsquare.com'
# Explicit source pages: add verified pages here rather than crawling the database.
SOURCES = [
    ('Patek Philippe', 'Nautilus', '', '/en/watches/patek-philippe/nautilus/lpi'),
    *[('Patek Philippe', 'Nautilus', ref, f'/en/watches/patek-philippe/nautilus/ref-patek-philippe-{ref}/lpi') for ref in ('3700', '3800', '5711', '5712')],
    ('Patek Philippe', 'Calatrava', '', '/en/watches/patek-philippe/calatrava/lpi'),
    ('Patek Philippe', 'Aquanaut', '', '/en/watches/patek-philippe/aquanaut/lpi'),
    ('Cartier', 'Pasha', '', '/en/watches/cartier/pasha/lpi'),
    ('Cartier', 'Tank', '', '/en/watches/cartier/tank/lpi'),
    ('Cartier', 'Santos', '', '/en/watches/cartier/santos/lpi'),
]


def parse_chart(html):
    soup = BeautifulSoup(html, 'html.parser')
    widget = soup.select_one('[data-chart-init-code-function-name]')
    if widget is None:
        raise ValueError('Public chart missing; retain previous snapshot')
    name = widget['data-chart-init-code-function-name']
    pattern = r'function\s+' + re.escape(name) + r'\s*\(\)\s*\{\s*return\s*\((\[.*?\])\)\s*;'
    code = '\n'.join(script.get_text() for script in widget.find_all('script'))
    match = re.search(pattern, code, re.S)
    if not match:
        raise ValueError('Chart schema changed')
    raw = json.loads(match.group(1))  # Never evaluate source JavaScript.
    if not isinstance(raw, list) or not raw:
        raise ValueError('Empty chart')
    observations, excluded = [], 0
    for item in raw:
        if not isinstance(item, list) or len(item) != 2:
            raise ValueError('Unexpected chart point')
        ts, value = item
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in item):
            raise ValueError('Invalid numeric point')
        if not 0 <= ts <= datetime.now(timezone.utc).timestamp() * 1000:
            raise ValueError('Unexpected chart date')
        # Keep positive low outliers visible; no silent price-based trimming.
        if value <= 0:
            excluded += 1
            continue
        observations.append([int(ts), value])
    if not observations:
        raise ValueError('No positive observations')
    # Identical points may be different lots: do not deduplicate or invent identities.
    observations.sort(key=lambda p: p[0])
    return observations, excluded


def summarize(points):
    years = {}
    for ts, price in points:
        year = datetime.fromtimestamp(ts / 1000, timezone.utc).year
        years.setdefault(year, []).append(price)
    return [dict(year=y, count=len(p), median=round(median(p), 2), low=min(p), high=max(p))
            for y, p in sorted(years.items())]


def refresh(output, cache, limit=None):
    output, cache = Path(output), Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    previous = json.loads(output.read_text()) if output.exists() else {'series': []}
    by_url = {s['source_url']: s for s in previous['series']}
    checked = datetime.now(timezone.utc).isoformat()
    failures, successful = [], 0
    session = requests.Session()
    session.headers['User-Agent'] = 'WatchRadar/1.0 (public historical chart research)'
    for brand, model, reference, path in SOURCES[:limit]:
        url = BASE + path
        try:
            r = session.get(url, timeout=40)
            r.raise_for_status()
            if r.url.rstrip('/') != url.rstrip('/'):
                raise ValueError('Source redirected; identity needs review')
            points, excluded = parse_chart(r.text)
            source_id = hashlib.sha256(url.encode()).hexdigest()[:16]
            (cache / f'{source_id}.html').write_text(r.text)
            by_url[url] = dict(id=source_id, brand=brand, model=model, reference=reference,
                scope='reference_family' if reference else 'collection', currency='EUR',
                currency_basis='Public source chart tooltip and y-axis specify eur / k €',
                price_basis='source_chart_reported; buyer premium and historical FX unverified',
                source_url=url, source='Collector Square LuxPrice-Index', retrieved_at=checked,
                checked_at=checked, state='ok', source_sha256=hashlib.sha256(r.content).hexdigest(),
                points=points, annual=summarize(points), excluded_nonpositive=excluded,
                independent_source_count=1, scoring_enabled=False)
            successful += 1
            print(f'{brand} {model} {reference}: {len(points)} chart observations')
        except (requests.RequestException, ValueError, KeyError) as exc:
            failures.append({'source_url': url, 'error': str(exc), 'checked_at': checked})
            if url in by_url:
                by_url[url] = {**by_url[url], 'state': 'stale', 'checked_at': checked, 'error': str(exc)}
            print(f'FAILED {url}: {exc}', file=sys.stderr)
        time.sleep(1)
    if not by_url:
        raise RuntimeError('No validated history available; output unchanged')
    payload = dict(schema_version=1, checked_at=checked, series=list(by_url.values()), errors=failures,
        limitations=['Public chart observations only, not the complete transaction database',
                      'Collection and reference-family series overlap; never pool their counts',
                      'Mixed materials, variants and conditions; no independent price verification',
                      'Dates and EUR values reproduced from chart; fees and FX basis unverified'])
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix('.tmp')
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    temporary.replace(output)
    return successful, failures


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='docs/price_history.json')
    parser.add_argument('--cache', default='tmp/collector_square')
    parser.add_argument('--limit', type=int)
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error('--limit must be positive')
    count, errors = refresh(args.output, args.cache, args.limit)
    if errors:
        sys.exit(1)
