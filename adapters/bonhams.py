"""Opt-in Bonhams pilot. Public SSR catalogue with verified ?page=N pagination."""
import re
import time
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
    # Pilot includes only verified sale results and clearly upcoming catalogues.
    # Never label unsold/withdrawn lots as sold or invent a live bid.
    if state == 'SOLD':
        status = 'past'
    elif state == 'NEW' and not ended:
        status = 'upcoming'
    else:
        return None
    price = r.get('price') or {}
    sold = amount(price.get('hammerPrice')) if status == 'past' else None
    if status == 'past' and sold is None:
        return None
    date = (r.get('auctionEndDate') or {}).get('datetime', '')[:10]
    return Lot(lot_id='bonhams_' + r['id'], platform='Bonhams', platform_type='major_house',
        source_url=f"{BASE}/auction/{r['auctionId']}/lot/{r['lotNo']['full']}/{r['slug']}/",
        auction_name=auction['sSaleName'], auction_date=date,
        lot_number=r['lotNo']['full'], brand=brand, brand_matched_keyword=keyword,
        title_raw=title, estimate_low=amount(price.get('estimateLow')),
        estimate_high=amount(price.get('estimateHigh')), estimate_currency=r['currency']['iso_code'],
        sold_price=sold, sold_price_basis='hammer' if sold else '',
        status=status, image_url=(r.get('image') or {}).get('url', ''),
        manual_review=True, scoring_enabled=False)

def fetch_sale(url, max_pages=20):
    records = {}; total = None; auction = None
    for page in range(1, max_pages + 1):
        p = page_data(fetch(url if page == 1 else url + f'?page={page}'))
        auction = p['auction']; data = p['lotData']; total = int(data['nbHits'])
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

def run():
    global LAST_REPORT
    LAST_REPORT = {'scope': 'department-linked sales, pilot', 'sales': [], 'errors': []}
    urls = discover(fetch(DEPARTMENT))
    if not urls:
        raise ValueError('No watch sales discovered')
    lots = []
    for url in urls[:8]:
        try:
            found, report = fetch_sale(url)
            lots.extend(found); LAST_REPORT['sales'].append(report)
        except Exception as e:
            LAST_REPORT['errors'].append({'url': url, 'error': str(e)})
            print(f'[bonhams] failed {url}: {e}')
    if len(urls) > 8:
        LAST_REPORT['errors'].append({'error': 'Discovery capped at 8 sales'})
    return lots
