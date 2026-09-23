"""Opt-in Sotheby's catalogue pilot using the official public pagination query."""
import re
import time
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from .base import Lot, match_brand, normalize_end
from .item_filter import exclusion_reason
from .market_common import fetch, page_data, amount

BASE = 'https://www.sothebys.com'
DEPARTMENT = BASE + '/en/departments/watches'
LAST_REPORT = {}
GRAPHQL_URL = 'https://clientapi.prod.sothelabs.com/graphql'
LOT_QUERY = Path(__file__).with_name('sothebys_lots.graphql').read_text()

def discover(html):
    soup = BeautifulSoup(html, 'html.parser')
    return list(dict.fromkeys(a['href'].rstrip('/') for a in soup.select('a[href]')
        if re.fullmatch(r'https://www\.sothebys\.com/en/buy/auction/\d{4}/[^/]+/?', a['href'])
        and 'watch' in a['href'].lower()))

def parse_sale(html):
    p = page_data(html); cache = p['apolloCache']
    auction = next(v for v in cache.values() if v.get('__typename') == 'Auction')
    if 'Watches' not in auction.get('departmentNames', []):
        raise ValueError('Not a verified watch catalogue')
    cards = [v for v in cache.values() if v.get('__typename') == 'LotCard']
    if not cards and p['totalLotCount']:
        raise ValueError('Catalogue cards missing')
    lots = parse_cards(cards, auction, cache)
    return lots, {'catalogue_records': len(cards), 'expected_records': p['totalLotCount'],
                  'retained': len(lots), 'complete': len(cards) == p['totalLotCount']}


def parse_cards(cards, auction, cache=None):
    cache = cache or {}
    lots = []
    for r in cards:
        title = ' '.join(filter(None, [r.get('creatorsDisplayTitle'), r.get('title')]))
        brand, keyword = match_brand(title)
        if not brand or exclusion_reason(title):
            continue
        if (r.get('withdrawnState') or {}).get('state') != 'NotAffected':
            continue
        bid = r.get('bidState') or {}
        if '__ref' in bid:
            bid = cache.get(bid['__ref'], {})
        phase = (bid.get('bidTypeV2') or {}).get('timedBidPhase')
        # Only the verified pre-bidding schema is enabled in this first pilot.
        # Closed results need separate hammer/all-in reconciliation.
        if bid.get('isClosed') is not False or phase != 'Published':
            continue
        estimate = r.get('estimateV2') or {}; slug = auction['slug']
        media = next((v for k,v in r.items() if k == 'media' or k.startswith('media(')), {})
        images = media.get('images') or []
        renditions = images[0].get('renditions', []) if images else []
        image = next((v.get('url','') for v in renditions if v.get('imageSize') == 'Small'), '')
        lots.append(Lot(lot_id='sothebys_'+r['lotId'], platform="Sotheby's", platform_type='major_house',
            source_url=f"{BASE}/en/buy/auction/{slug['year']}/{slug['name']}/{r['slug']['lotSlug']}",
            auction_name=auction['title'], auction_date=(auction.get('dates') or {}).get('startsToClose','')[:10],
            ends_at=normalize_end(bid.get('closingTime')),
            lot_number=r['lotNumber']['lotDisplayNumber'], brand=brand, brand_matched_keyword=keyword,
            title_raw=title, estimate_currency=auction['currencyV2'],
            estimate_low=amount(estimate.get('lowEstimate')), estimate_high=amount(estimate.get('highEstimate')),
            status='upcoming', image_url=image, manual_review=True, scoring_enabled=False))
    return lots


def request_page(auction_id, offset, limit):
    response = requests.post(GRAPHQL_URL, json={
        'query': LOT_QUERY,
        'variables': {'id': auction_id, 'offset': offset, 'limit': limit}}, timeout=35)
    response.raise_for_status()
    payload = response.json()
    if payload.get('errors'):
        raise ValueError('Public catalogue query returned errors')
    auction = (payload.get('data') or {}).get('auction')
    if not auction or auction.get('auctionId') != auction_id:
        raise ValueError('Missing or mismatched auction')
    if 'Watches' not in auction.get('departmentNames', []):
        raise ValueError('Not a verified watch catalogue')
    return auction


def fetch_sale(url, max_pages=40):
    # Resolve the public catalogue UUID from the official sale page, not a seed list.
    p = page_data(fetch(url))
    auction_id = p['auctionId']
    records = {}; expected = None; offset = 0; pages = []
    for _ in range(max_pages):
        auction = request_page(auction_id, offset, 48)
        connection = auction.get('lotCardsConnection') or {}
        total = connection.get('totalCount')
        batch = connection.get('lots')
        more = connection.get('hasNextPage')
        if type(total) is not int or total < 0 or not isinstance(batch, list) or type(more) is not bool:
            raise ValueError('Invalid pagination metadata')
        if expected is None:
            expected = total
        elif total != expected:
            raise ValueError('Catalogue total changed during pagination; retry next run')
        before = len(records)
        for r in batch:
            if not r.get('lotId'):
                raise ValueError('Missing lot identity')
            records[r['lotId']] = r
        pages.append({'offset': offset, 'returned': len(batch), 'new_unique': len(records)-before})
        if len(records) > expected:
            raise ValueError('Catalogue exceeds reported total')
        if not more:
            if len(records) != expected:
                raise ValueError(f'Incomplete catalogue: {len(records)}/{expected}')
            lots = parse_cards(list(records.values()), auction)
            return lots, {'catalogue_records':len(records), 'expected_records':expected,
                          'retained':len(lots), 'complete':True, 'pages':pages}
        if len(records) == before:
            raise ValueError('Pagination made no progress; repeated or empty page')
        if len(records) == expected:
            raise ValueError('Inconsistent hasNextPage at catalogue total')
        offset += len(batch)
        time.sleep(1)
    raise ValueError('Pagination safety limit reached; refusing partial catalogue')


def run():
    global LAST_REPORT
    LAST_REPORT = {'scope':'department-linked sales, complete paginated catalogues', 'sales':[], 'errors':[]}
    urls = discover(fetch(DEPARTMENT))
    if not urls:
        raise ValueError('No watch sales discovered')
    lots = []
    for url in urls[:8]:
        try:
            found, report = fetch_sale(url); report['url'] = url
            LAST_REPORT['sales'].append(report); lots.extend(found)
            if not report['complete']:
                print(f"[sothebys] partial catalogue: {report['catalogue_records']}/{report['expected_records']}")
        except Exception as e:
            LAST_REPORT['errors'].append({'url':url, 'error':str(e)})
            print(f'[sothebys] failed {url}: {e}')
    return lots
