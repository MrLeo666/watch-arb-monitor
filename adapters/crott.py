# adapters/crott.py — VERIFIED 2026-09: Auktionen Dr. Crott (uhren-muser.de).
# /en/api/auction and /en/api/products return JSON even when Content-Type is
# text/html. Auction metadata drives sale identity + status (do not hardcode a
# future sale). The product list is the current catalogue; a not-yet-published
# next date in next_auction is ignored until lots appear in /api/products.
# List rows have estimates but no image hrefs / bid fields. Per-id
# /en/api/products/{id} adds maxBid, hammerPrice, realizedPrice, and images.*.href
# (relative, e.g. images/7/63080/jpg/7_63080_1.jpg → https://uhren-muser.de/...).
# Lot page (200): /en/catalogue/{id}. JSON has no currency field; site prints
# euros, so estimates are treated as EUR. No buyers-premium field — leave None.
# hammer/realized may stay 0 after bids; keep maxBid as current_bid, do not
# invent a hammer.
import json
import re
import time
import requests
from .base import Lot, match_brand, MANUAL_REVIEW_BRANDS

BASE = "https://uhren-muser.de"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
           "Accept": "application/json, text/plain, */*",
           "Accept-Language": "en,de;q=0.8"}


def _get_json(url):
    """Parse JSON bodies even when the server labels them text/html."""
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    try:
        return r.json()
    except ValueError:
        return json.loads(r.text)


def _flag(v):
    return v in (True, 1, "1", "true", "True")


def _plain(html: str) -> str:
    t = re.sub(r"<br\s*/?>", " ", html or "", flags=re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _money(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _iso_date(*vals):
    for v in vals:
        if not v:
            continue
        m = re.search(r"(\d{4}-\d{2}-\d{2})", str(v))
        if m:
            return m.group(1)
    return ""


def _sale_status(meta: dict) -> str:
    if _flag(meta.get("liveauction")):
        return "live"
    if _flag(meta.get("isAuctionDone")):
        return "past"
    if _flag(meta.get("isBidsOpen")):
        return "live"
    return "upcoming"


def _abs_url(href: str) -> str:
    href = (href or "").strip()
    if not href:
        return ""
    if href.startswith("http://") or href.startswith("https://"):
        return href
    return f"{BASE}/{href.lstrip('/')}"


def _image_href(images) -> str:
    """First JPEG (else any) href from per-id images.small/large/tiny entries."""
    if not isinstance(images, dict):
        return ""
    for size in ("small", "large", "tiny"):
        arr = images.get(size)
        if not isinstance(arr, list):
            continue
        for entry in arr:
            if not isinstance(entry, dict):
                continue
            jpeg, other = "", ""
            for v in entry.values():
                if not isinstance(v, dict):
                    continue
                href = v.get("href") or ""
                if not href:
                    continue
                fmt = str(v.get("format") or "").upper()
                if fmt == "JPEG" or href.lower().endswith(".jpg"):
                    jpeg = href
                    break
                if not other:
                    other = href
            if jpeg or other:
                return jpeg or other
    return ""


def _title(rec: dict) -> str:
    brand = rec.get("brand") or rec.get("brandFilter") or ""
    nick = rec.get("nickName") or ""
    headline = _plain(rec.get("headline") or "")
    feats = rec.get("specificFeatures") or {}
    ref = feats.get("reference") if isinstance(feats, dict) else ""
    parts = [p for p in (brand, nick, headline) if p]
    title = " ".join(parts)
    if ref and str(ref).lower() not in title.lower():
        title = f"{title} Ref. {ref}".strip()
    return title[:160]


def _match_text(rec: dict) -> str:
    feats = rec.get("specificFeatures") or {}
    ref = feats.get("reference") if isinstance(feats, dict) else ""
    return " ".join(str(x) for x in (
        rec.get("brand") or "",
        rec.get("brandFilter") or "",
        rec.get("nickName") or "",
        _plain(rec.get("headline") or ""),
        rec.get("category") or "",
        ref or "",
    ))


def _sold_price(rec: dict):
    # Do not invent a hammer from maxBid when realized/hammer stay 0.
    for key in ("realizedPrice", "hammerPrice"):
        v = _money(rec.get(key))
        if v is not None and v > 0:
            return v
    return None


def _current_bid(rec: dict):
    v = _money(rec.get("maxBid"))
    if v is not None and v > 0:
        return v
    return None


def _lot_from_rec(rec: dict, meta: dict, status: str, auction_name: str, auction_date: str):
    pid = str(rec.get("id") or "")
    if not pid:
        return None
    brand, kw = match_brand(_match_text(rec))
    if not brand:
        return None
    auction = rec.get("auction")
    if auction is None:
        auction = meta.get("current_auction") or meta.get("id") or ""
    sold = _sold_price(rec)
    img = _abs_url(_image_href(rec.get("images")))
    return Lot(
        lot_id=f"crott_{auction}_{pid}",
        platform="Dr. Crott", platform_type="regional",
        source_url=f"{BASE}/en/catalogue/{pid}",
        auction_name=auction_name,
        auction_date=auction_date,
        lot_number=str(rec.get("lotId") or ""),
        brand=brand, brand_matched_keyword=kw,
        title_raw=_title(rec),
        estimate_low=_money(rec.get("estimatedLow")),
        estimate_high=_money(rec.get("estimatedHigh")),
        estimate_currency="EUR",  # inferred: payload has no currency; site prints €
        current_bid=_current_bid(rec),
        sold_price=sold,
        status=status,
        buyers_premium_pct=None,
        image_url=img,
        manual_review=brand in MANUAL_REVIEW_BRANDS,
    )


def run():
    out = []
    try:
        meta = _get_json(f"{BASE}/en/api/auction")
        if not isinstance(meta, dict):
            print("[crott] auction metadata was not an object")
            return out
    except Exception as e:
        print(f"[crott] auction metadata failed: {e}")
        return out

    sale_id = meta.get("id") or meta.get("current_auction")
    auction_name = f"Auktionen Dr. Crott {sale_id}" if sale_id else "Auktionen Dr. Crott"
    auction_date = _iso_date(
        meta.get("endDateOnlineAuction"),
        meta.get("endDate"),
        meta.get("date"),
    )
    status = _sale_status(meta)
    print(f"[crott] sale {sale_id} status={status} date={auction_date} "
          f"done={meta.get('isAuctionDone')} live={meta.get('liveauction')} "
          f"next={meta.get('next_auction')}")

    try:
        products = _get_json(f"{BASE}/en/api/products")
    except Exception as e:
        print(f"[crott] products failed: {e}")
        return out
    if not isinstance(products, list):
        print("[crott] products payload was not a list")
        return out

    candidates = []
    for rec in products:
        if not isinstance(rec, dict) or _flag(rec.get("isWithdrawn")):
            continue
        if match_brand(_match_text(rec))[0]:
            candidates.append(rec)
    print(f"[crott] {len(products)} products, {len(candidates)} whitelist")

    for rec in candidates:
        pid = rec.get("id")
        detail = rec
        if pid:
            try:
                extra = _get_json(f"{BASE}/en/api/products/{pid}")
                if isinstance(extra, dict) and extra.get("id"):
                    detail = {**rec, **extra}
            except Exception as e:
                print(f"[crott] product {pid} detail failed: {e}")
            time.sleep(1.0)
        lot = _lot_from_rec(detail, meta, status, auction_name, auction_date)
        if lot:
            out.append(lot)
    print(f"[crott] {len(out)} whitelist lots")
    return out
