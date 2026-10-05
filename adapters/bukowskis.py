"""Public Nordic online watch catalogue. Pilot: bids are not sale results."""
import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from .base import Lot, match_brand
from .item_filter import exclusion_reason
from .market_common import fetch

BASE = 'https://www.bukowskis.com'
CATALOGUE = BASE + '/en/lots/category/38-timepieces'
LAST_REPORT = {}


def money(text):
    m = re.fullmatch(r'([\d\s\u00a0]+)\s+(SEK|EUR)', text.strip())
    return (float(re.sub(r'\s', '', m[1])), m[2]) if m else (None, '')


def parse_page(html, now=None):
    now = now or datetime.now(timezone.utc)
    soup = BeautifulSoup(html, 'html.parser')
    count = soup.select_one('#lot-result-count')
    if count is None or not re.fullmatch(r'[\d\s,]+ items?', count.get_text(strip=True)):
        raise ValueError('Expected public catalogue count missing')
    total = int(re.sub(r'\D', '', count.get_text()))
    rows = soup.select('.c-lot-index-lot[data-lot-id]')
    ids, lots = set(), []
    for row in rows:
        rid = row['data-lot-id']; ids.add(rid)
        def text(selector):
            el = row.select_one(selector)
            return el.get_text(' ', strip=True) if el else ''
        title = ' '.join(filter(None, [text('.c-lot-index-lot__artist'), text('.c-lot-index-lot__title')]))
        brand, keyword = match_brand(title)
        # Category includes clocks and accessories; require an explicit wristwatch.
        if not brand or exclusion_reason(title) or not re.search(r'\bwristwatch\b', title, re.I):
            continue
        link = row.select_one('a.c-lot-index-lot__title-link[href]')
        if not link:
            raise ValueError('Watch source link missing')
        url = urljoin(BASE, link['href'])
        if urlparse(url).netloc != 'www.bukowskis.com':
            raise ValueError('Unexpected source link')
        est, currency = money(text('.c-lot-index-lot__estimate-value'))
        bid, bid_currency = money(text('.c-lot-index-lot__result-value'))
        caption = text('.c-lot-index-lot__result-caption')
        clock = row.select_one('[data-end-date]')
        end = datetime.fromtimestamp(int(clock['data-end-date']), timezone.utc) if clock else None
        status = 'live' if end and end > now and caption in ('Current bid', 'No bids') else 'unknown'
        if end and end <= now: status = 'ended'
        currency = currency or bid_currency
        if caption != 'Current bid' or bid_currency != currency or status != 'live': bid = None
        image = row.select_one('img.o-aspect-ratio__image')
        lots.append(Lot(lot_id='bukowskis_' + rid, platform='Bukowskis', platform_type='regional',
            source_url=url, title_raw=title, brand=brand, brand_matched_keyword=keyword,
            lot_number=text('.c-lot-index-lot__catalogue-number'),
            auction_name=text('.c-lot-index-lot__extra-link') or 'Bukowskis Online',
            auction_date=end.date().isoformat() if end else '', ends_at=end.isoformat() if end else '',
            estimate_low=est, estimate_currency=currency, current_bid=bid,
            image_url=image.get('src','') if image else '', status=status, source_status=caption,
            manual_review=True, scoring_enabled=False))
    pages = [urljoin(BASE, a['href']) for a in soup.select('.c-toolbar__pagination a[href]')]
    if any(urlparse(p).netloc != 'www.bukowskis.com' or not urlparse(p).path.startswith('/en/lots/category/38-timepieces') for p in pages):
        raise ValueError('Unexpected pagination link')
    return lots, ids, total, pages


def run():
    global LAST_REPORT
    LAST_REPORT = {'scope': 'Nordic online wristwatches, pilot', 'sales': [], 'errors': []}
    pending, seen, ids, lots, total = [CATALOGUE], set(), set(), {}, None
    while pending:
        url = pending.pop(0)
        if url in seen: continue
        if len(seen) >= 20: raise ValueError('Catalogue pagination exceeded 20 pages')
        seen.add(url)
        found, page_ids, expected, pages = parse_page(fetch(url))
        if total is not None and expected != total: raise ValueError('Catalogue changed during pagination')
        total = expected
        ids.update(page_ids)
        lots.update({l.lot_id:l for l in found})
        pending.extend(p for p in pages if p not in seen and p not in pending)
    if len(ids) != total: raise ValueError(f'Incomplete catalogue: {len(ids)}/{total}')
    LAST_REPORT['sales'] = [{'url':CATALOGUE,'catalogue_records':total,'retained':len(lots),'complete':True}]
    return list(lots.values())
