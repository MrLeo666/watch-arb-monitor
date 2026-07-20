# adapters/loupethis.py — VERIFIED 2026-07: public JSON:API at api.loupethis.com.
# Each "auction" is one lot on a rolling 7-day timed sale. USD, cents. BP field included.
# High buy-side value: live current bid lets us compute real-time margin vs fair value.
import requests
from .base import Lot, match_brand, MANUAL_REVIEW_BRANDS

API = "https://api.loupethis.com/api/v1/auctions"
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

def run():
    out = []
    page = 1
    while True:
        try:
            r = requests.get(API, params={"status": "active", "page": page},
                             headers=HEADERS, timeout=30)
            r.raise_for_status()
            d = r.json()
        except Exception as e:
            print(f"[loupethis] page {page} failed: {e}")
            break
        for rec in d.get("data", []):
            a = rec.get("attributes", {})
            title = a.get("title", "")
            brand, kw = match_brand(title)
            if not brand:
                continue
            bid_c = a.get("current_bid_price_cents")
            out.append(Lot(
                lot_id=f"loupethis_{rec.get('id')}",
                platform="Loupe This", platform_type="online",
                source_url=f"https://loupethis.com/auctions/{a.get('slug','')}",
                auction_name="Loupe This rolling sale",
                auction_date=(a.get("ends_at") or "")[:10],
                lot_number=str(a.get("lot", "")),
                brand=brand, brand_matched_keyword=kw, title_raw=title,
                estimate_currency="USD",
                current_bid=(bid_c / 100.0) if bid_c else None,
                status="live",
                buyers_premium_pct=float(a.get("buyers_premium_percent") or 10),
                image_url=a.get("featured_image_url", ""),
                manual_review=brand in MANUAL_REVIEW_BRANDS,
            ))
        pg = (d.get("meta") or {}).get("pagination") or {}
        if not pg.get("next_page"):
            break
        page = pg["next_page"]
    print(f"[loupethis] {len(out)} whitelist lots")
    return out
