# adapters/bezel.py — VERIFIED 2026-07: /auctions embeds full listing array in
# __NEXT_DATA__ (props.pageProps.auctions, ~400 records). USD cents, live bids,
# structured brand, images. Buyer's premium: 0%.
import json
import re
import requests
from .base import Lot, match_brand, MANUAL_REVIEW_BRANDS

URL = "https://shop.getbezel.com/auctions"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}

def run():
    out = []
    try:
        html = requests.get(URL, headers=HEADERS, timeout=40).text
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
        recs = json.loads(m.group(1))["props"]["pageProps"]["auctions"]
    except Exception as e:
        print(f"[bezel] fetch failed: {e}")
        return out
    for r in recs:
        mdl = r.get("model") or {}
        brand_obj = mdl.get("brand") or {}
        brand_name = brand_obj.get("displayName") or brand_obj.get("name") or ""
        title = f"{brand_name} {mdl.get('displayName') or mdl.get('name') or ''}".strip()
        brand, kw = match_brand(title)
        if not brand:
            continue
        info = r.get("auctionInfo") or {}
        bid_c = ((info.get("highestBid") or {}).get("priceCents")
                 or info.get("startingPriceCents"))
        img = ""
        for im in (r.get("images") or []):
            iobj = im.get("image") or {}
            img = iobj.get("cloudinaryUrl") or iobj.get("rawUrl") or ""
            if im.get("type") == "FRONT" and img:
                break
        status = "live" if info.get("live") and not info.get("ended") else (
            "past" if info.get("ended") else "upcoming")
        out.append(Lot(
            lot_id=f"bezel_{r.get('id')}",
            platform="Bezel", platform_type="online",
            source_url=f"https://shop.getbezel.com/listings/{r.get('id')}",
            auction_name="Bezel Auctions",
            auction_date=(info.get("endDate") or "")[:10],
            brand=brand, brand_matched_keyword=kw, title_raw=title,
            estimate_currency="USD",
            current_bid=(bid_c / 100.0) if bid_c else None,
            status=status,
            buyers_premium_pct=0.0,
            image_url=img,
            manual_review=brand in MANUAL_REVIEW_BRANDS,
        ))
    print(f"[bezel] {len(out)} whitelist lots")
    return out
