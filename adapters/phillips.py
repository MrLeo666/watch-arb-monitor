# adapters/phillips.py — VERIFIED 2026-07: watch sale codes discoverable on /watches,
# lot tiles server-rendered in auction page HTML once sale status is OPEN/PAST.
# Tile text: "<lot#> | <maker> | <model> | Estimate | CHF40,000–80,000 [| Sold For | CHF82,550]"
import re
import time
import json
import requests
from bs4 import BeautifulSoup
from .base import Lot, match_brand, MANUAL_REVIEW_BRANDS

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}
BASE = "https://www.phillips.com"
EST_RE = re.compile(r"([A-Z]{3})\s?([\d,]+)\s*[–\-]\s*(?:[A-Z]{3}\s?)?([\d,]+)")
PRICE_RE = re.compile(r"([A-Z]{3})\s?([\d,]+)")

def discover_watch_sales():
    """Watch department sale codes follow <LOC>08<seq><yy>; scrape them from /watches."""
    r = requests.get(f"{BASE}/watches", headers=HEADERS, timeout=30)
    r.raise_for_status()
    codes = sorted(set(re.findall(r"/auction/([A-Z]{2}08\d{4})", r.text)))
    return codes

def _num(s):
    try:
        return float(s.replace(",", ""))
    except Exception:
        return None

def fetch_auction(sale_code: str):
    url = f"{BASE}/auction/{sale_code}"
    r = requests.get(url, headers=HEADERS, timeout=40)
    r.raise_for_status()
    html = r.text

    status_m = re.search(r'auctionStatus\\+",\\+"([A-Z_]+)', html)
    status_raw = status_m.group(1) if status_m else ""
    if status_raw == "HIGHLIGHTS_ONLY":
        return []  # lots not yet published

    soup = BeautifulSoup(html, "html.parser")

    # Auction name + end date from ld+json Event
    auction_name, auction_date = sale_code, ""
    for s in soup.find_all("script", type="application/ld+json"):
        try:
            d = json.loads(s.string or "")
        except Exception:
            continue
        if isinstance(d, dict) and d.get("@type") == "Event":
            auction_name = d.get("name", sale_code)
            auction_date = (d.get("endDate") or d.get("startDate") or "")[:10]
            break

    lot_status = "past" if status_raw == "PAST" else "upcoming"
    lots, seen = [], set()
    for a in soup.select("a[href*='/detail/']"):
        href = a.get("href", "")
        if "/detail/" not in href or href in seen:
            continue
        # climb one level: tile container is the anchor's parent grid item
        tile = a.parent
        text = tile.get_text(" | ", strip=True) if tile else a.get_text(" | ", strip=True)
        if "Estimate" not in text:
            continue
        seen.add(href)
        brand, kw = match_brand(text)
        if not brand:
            continue
        parts = [p.strip() for p in text.split("|")]
        lot_number = parts[0] if parts and parts[0].isdigit() else ""
        est = EST_RE.search(text)
        cur, lo, hi = (est.group(1), _num(est.group(2)), _num(est.group(3))) if est else ("", None, None)
        sold = None
        if "Sold For" in text:
            m = PRICE_RE.search(text.split("Sold For", 1)[1])
            if m:
                sold = _num(m.group(2))
        img = ""
        img_el = tile.find("img") if tile else None
        if img_el:
            img = img_el.get("src", "")
        lots.append(Lot(
            lot_id=f"phillips_{sale_code}_{lot_number or href.rsplit('/', 1)[-1]}",
            platform="Phillips", platform_type="major_house",
            source_url=href if href.startswith("http") else BASE + href,
            auction_name=auction_name, auction_date=auction_date,
            lot_number=lot_number, brand=brand, brand_matched_keyword=kw,
            title_raw=" ".join(parts[1:3]) if len(parts) >= 3 and parts[0].isdigit() else " ".join(parts[:3])[:160],
            estimate_low=lo, estimate_high=hi, estimate_currency=cur,
            sold_price=sold, status=lot_status,
            buyers_premium_pct=27.0,  # watches first tier (Geneva/HK 2026 rate card)
            image_url=img,
            manual_review=brand in MANUAL_REVIEW_BRANDS,
        ))
    return lots

def run():
    out = []
    try:
        codes = discover_watch_sales()
    except Exception as e:
        print(f"[phillips] discovery failed: {e}")
        return out
    print(f"[phillips] watch sales: {codes}")
    for code in codes:
        try:
            lots = fetch_auction(code)
            print(f"[phillips] {code}: {len(lots)} whitelist lots")
            out += lots
        except Exception as e:
            print(f"[phillips] {code} failed: {e}")
        time.sleep(2)  # polite delay
    return out
