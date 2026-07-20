# adapters/allu.py — VERIFIED 2026-07: allu-auction.com (Valuence, Japan).
# Public catalog at /lot/{n} ("nth Auction") embeds APP.data = JSON.parse('...')
# with article.showLotList: maker, model_name_en, reference_no, estimate_low/high
# (JPY), starting_price, box/papers flags, thumbnail_url, exhibit_at.
# Notes: viewing is public; BIDDING requires dealer membership. Past auctions do
# not expose realized prices publicly. Individual item pages are modal-only, so
# source_url points at the auction catalog page (find by lot number).
import codecs
import json
import re
import time
import requests
from .base import Lot, match_brand, MANUAL_REVIEW_BRANDS

BASE = "https://www.allu-auction.com"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
           "Accept-Language": "ja,en"}

def _app_data(n):
    r = requests.get(f"{BASE}/lot/{n}", headers=HEADERS, timeout=30)
    if r.status_code != 200:
        return None
    m = re.search(r"APP\.data = JSON\.parse\('(.*?)'\)", r.text, re.S)
    if not m:
        return None
    s = codecs.decode(m.group(1).replace("\\'", "'"), "unicode_escape")
    try:
        return json.loads(s)
    except Exception:
        return None

def _url(u):
    return (u or "").replace("\\/", "/")

def run():
    out = []
    misses = 0
    n = 1
    while misses < 2 and n < 40:
        d = _app_data(n)
        if not d or not (d.get("article") or {}).get("showLotList"):
            misses += 1
            n += 1
            continue
        misses = 0
        art = d["article"]
        upcoming = bool(art.get("is_before_end_auction"))
        title_info = art.get("get_title_image") or {}
        auction_name = f"ALLU {title_info.get('auction_title') or f'{n}th Auction'}"
        auction_date = ""
        m = re.search(r"(\d{4})-(\d{2})-(\d{2})", str(art.get("pre_bid_end") or ""))
        if m:
            auction_date = m.group(0)
        if upcoming:  # past ALLU sales expose no realized prices — skip them
            for l in art["showLotList"]:
                maker = l.get("maker") or ""
                model = l.get("model_name_en") or l.get("model_name") or ""
                ref = l.get("reference_no") or ""
                title = f"{maker} {model}" + (f" Ref. {ref}" if ref else "")
                brand, kw = match_brand(f"{maker} {model}")
                if not brand:
                    continue
                extras = []
                if l.get("box"):
                    extras.append("Box")
                if l.get("papers"):
                    extras.append("Papers")
                if extras:
                    title += f" ({'/'.join(extras)})"
                out.append(Lot(
                    lot_id=f"allu_{n}_{l.get('lot_no') or l.get('item_id')}",
                    platform="ALLU Auction", platform_type="regional",
                    source_url=f"{BASE}/lot/{n}",
                    auction_name=auction_name,
                    auction_date=auction_date,
                    lot_number=str(l.get("lot_no") or ""),
                    brand=brand, brand_matched_keyword=kw,
                    title_raw=title[:160],
                    estimate_low=l.get("estimate_low"),
                    estimate_high=l.get("estimate_high"),
                    estimate_currency="JPY",
                    status="upcoming",
                    buyers_premium_pct=None,  # dealer auction; fee per membership terms
                    image_url=_url(l.get("thumbnail_url")),
                    manual_review=brand in MANUAL_REVIEW_BRANDS,
                ))
        n += 1
        time.sleep(1.5)
    print(f"[allu] {len(out)} whitelist lots")
    return out
