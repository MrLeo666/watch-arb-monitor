"""Opt-in Bonhams pilot. Public SSR catalogue with verified ?page=N pagination."""
import re
import time
import json
from datetime import datetime, timezone
from pathlib import Path
from .base import Lot, match_brand
from .item_filter import exclusion_reason
from .market_common import fetch, page_data, amount

BASE = 'https://www.bonhams.com'
DEPARTMENT = BASE + '/department/WCH/watches/'
LAST_REPORT = {}

def discover(html):
    auctions = page_data(html)['auctions']
    return list(dict.fromkeys(
        f"{BASE}/auction/{a['id']}/{a['slug']}/" for a in auctions
        if any(d.get('code') == 'WCH' for d in a.get('departments', []))
        and str(a.get('id', '')).isdigit() and re.fullmatch(r'[a-z0-9-]+', a.get('slug', ''))))

def parse_record(r, auction):
    title = r.get('title') or ''
    brand, keyword = match_brand(title)
    if not brand or exclusion_reason(title):
        return None
    state = r.get('status', '')
    ended = (r.get('flags') or {}).get('isAuctionEnded') or r.get('auctionStatus') == 'FINISHED'
    # Keep unknown outcomes; never turn missing prices into sales.
    if state == 'SOLD':
        status = 'past'
    elif state == 'WITHDRAWN':
        status = 'withdrawn'
    elif state == 'UNSOLD':
        status = 'unsold'
    elif state == 'NEW' and not ended:
        start = (r.get('biddableFrom') or {}).get('timestamp')
        finish = (r.get('auctionEndDate') or {}).get('timestamp')
        now = datetime.now(timezone.utc).timestamp()
        if r.get('auctionBiddingStatus') == 'IP':
            status = 'live' if isinstance(start, (int, float)) and isinstance(finish, (int, float)) and start <= now < finish else 'unknown'
        else:
            status = 'upcoming'
    else:
        status = 'ended' if ended else 'unknown'
    price = r.get('price') or {}
    sold = amount(price.get('hammerPrice')) if status == 'past' else None
    date = (r.get('auctionEndDate') or {}).get('datetime', '')[:10]
    return Lot(lot_id='bonhams_' + r['id'], platform='Bonhams', platform_type='major_house',
        source_url=f"{BASE}/auction/{r['auctionId']}/lot/{r['lotNo']['full']}/{r['slug']}/",
        auction_name=auction['sSaleName'], auction_date=date,
        lot_number=r['lotNo']['full'], brand=brand, brand_matched_keyword=keyword,
        title_raw=title, estimate_low=amount(price.get('estimateLow')),
        estimate_high=amount(price.get('estimateHigh')), estimate_currency=r['currency']['iso_code'],
        sold_price=sold, sold_price_basis='hammer' if sold else '',
        status=status, source_status=state, sale_result='sold' if state == 'SOLD' else '', image_url=(r.get('image') or {}).get('url', ''),
        manual_review=True, scoring_enabled=False)

def fetch_sale(url, max_pages=20):
    records = {}; total = None; auction = None
    for page in range(1, max_pages + 1):
        p = page_data(fetch(url if page == 1 else url + f'?page={page}'))
        auction = p['auction']; data = p['lotData']; total = int(data['nbHits'])
        # The short /auction/ID/ redirect drops ?page=N. Use the published slug.
        sid, slug = str(auction.get('iSaleNo', '')), auction.get('slug', '')
        if sid.isdigit() and re.fullmatch(r'[a-z0-9-]+', slug):
            url = f'{BASE}/auction/{sid}/{slug}/'
        before = len(records)
        for r in data['auctionLots']:
            records[r['id']] = r
        if len(records) >= total:
            break
        if len(records) == before:
            raise ValueError(f'Incomplete catalogue: {len(records)}/{total}; repeated page')
        time.sleep(1)
    if len(records) != total:
        raise ValueError(f'Incomplete catalogue: {len(records)}/{total}')
    lots = [lot for r in records.values() if (lot := parse_record(r, auction))]
    return lots, {'url': url, 'catalogue_records': total, 'retained': len(lots), 'complete': True}

def known_sales(path=None):
    """Recheck previously observed sales even after department links rotate out."""
    path = path or Path(__file__).resolve().parents[1] / 'docs/lots.json'
    if not Path(path).exists(): return []
    rows = json.loads(Path(path).read_text())
    ids = []
    for lot in rows:
        if lot.get('platform') != 'Bonhams': continue
        match = re.match(r'https://www\.bonhams\.com/auction/(\d+)/', lot.get('source_url', ''))
        if match and match[1] not in ids: ids.append(match[1])
    return [f'{BASE}/auction/{sid}/' for sid in ids]


def run():
    global LAST_REPORT
    LAST_REPORT = {'scope': 'department-linked and previously observed sales, pilot', 'sales': [], 'errors': []}
    urls = []
    try:
        urls = discover(fetch(DEPARTMENT))
        if not urls: raise ValueError('No watch sales discovered')
    except Exception as e:
        LAST_REPORT['errors'].append({'url': DEPARTMENT, 'error': str(e)})
        print(f'[bonhams] discovery failed: {e}')
    sale_ids = {re.search(r'/auction/(\d+)/', u)[1] for u in urls}
    urls += [u for u in known_sales() if re.search(r'/auction/(\d+)/', u)[1] not in sale_ids]
    lots = []
    for url in urls[:12]:
        try:
            found, report = fetch_sale(url)
            lots.extend(found); LAST_REPORT['sales'].append(report)
        except Exception as e:
            LAST_REPORT['errors'].append({'url': url, 'error': str(e)})
            print(f'[bonhams] failed {url}: {e}')
    if len(urls) > 12:
        LAST_REPORT['errors'].append({'error': 'Discovery capped at 12 sales'})
        print('[bonhams] partial: discovery capped at 12 sales')
    return lots
