# adapters/watchcollecting.py — VERIFIED 2026-07: /auctions server-renders an
# Algolia InstantSearch state with rich hit records (productMake, currentBid,
# currencyCode, listingStage live/comingsoon/sold, priceSold, features.referenceNumber,
# noReserve, location, dtStageEndsUTC, mainImageUrl). ?query= and ?page= work via SSR.
# Strategy: one query per whitelist brand keyword, first 2 pages each.
import json
import re
import time
import requests
from .base import Lot, match_brand, MANUAL_REVIEW_BRANDS

BASE = "https://watchcollecting.com/auctions"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}

# One search term per brand — broad enough to catch, whitelist filter re-checks
SEARCH_TERMS = [
    "journe", "patek", "cartier", "akrivia", "rexhepi", "dufour", "voutilainen",
    "de bethune", "mb&f", "urwerk", "brette", "roger smith", "daniels",
    "greubel", "laurent ferrier", "gronefeld", "petermann", "lange",
    "daniel roth", "genta", "vianney halter", "romain gauthier", "urban jurgensen",
]

def _hits(url):
    t = requests.get(url, headers=HEADERS, timeout=30).text
    i = t.find('"hits":[')
    if i < 0:
        return []
    depth = 0
    j = i + 7
    for j in range(i + 7, len(t)):
        c = t[j]
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                break
    try:
        return json.loads(t[i + 7:j + 1])
    except Exception:
        return []

def run():
    out, seen = [], set()
    for term in SEARCH_TERMS:
        for page in (0, 1):
            url = f"{BASE}?query={requests.utils.quote(term)}" + (f"&page={page+1}" if page else "")
            try:
                hits = _hits(url)
            except Exception as e:
                print(f"[watchcollecting] {term} p{page} failed: {e}")
                break
            if not hits:
                break
            for hit in hits:
                hid = str(hit.get("id") or hit.get("objectID") or "")
                if not hid or hid in seen:
                    continue
                stage = hit.get("listingStage", "")
                title = (hit.get("title") or hit.get("collectionTitle") or "").strip()
                make = hit.get("productMake") or ""
                if make and make.lower() not in title.lower():
                    title = f"{make} {title}"
                ref = ((hit.get("features") or {}).get("referenceNumber") or "")
                if ref:
                    title = f"{title} Ref. {ref}"
                brand, kw = match_brand(f"{hit.get('productMake','')} {title}")
                if not brand:
                    continue
                seen.add(hid)
                cur = (hit.get("currencyCode") or "gbp").upper()
                status = {"live": "live", "comingsoon": "upcoming", "sold": "past"}.get(stage, "upcoming")
                sold = hit.get("priceSold") if status == "past" else None
                out.append(Lot(
                    lot_id=f"watchcollecting_{hid}",
                    platform="Watch Collecting", platform_type="online",
                    source_url=f"https://watchcollecting.com/for-sale/{hit.get('slug') or hid}",
                    auction_name=hit.get("collectionTitle") or "Watch Collecting",
                    auction_date=(hit.get("dtStageEndsUTC") or "")[:10],
                    brand=brand, brand_matched_keyword=kw, title_raw=title[:160],
                    estimate_currency=cur,
                    current_bid=hit.get("currentBid") if status == "live" else None,
                    sold_price=sold,
                    status=status,
                    buyers_premium_pct=10.0,  # approximate; verify per sale
                    image_url=hit.get("mainImageUrl", ""),
                    manual_review=brand in MANUAL_REVIEW_BRANDS,
                ))
            time.sleep(1.0)
    print(f"[watchcollecting] {len(out)} whitelist lots")
    return out
