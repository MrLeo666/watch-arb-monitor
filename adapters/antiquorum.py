# adapters/antiquorum.py — VERIFIED 2026-07: catalog.antiquorum.swiss is a
# server-rendered Rails app. /catalog lists current auction slug(s); lots are
# paginated at /en/auctions/{slug}/lots?page=N with schema.org microdata
# (priceCurrency + price = low estimate) and "EUR 1,200 - 2,200" style text.
import re
import time
import requests
from bs4 import BeautifulSoup
from .base import Lot, match_brand, MANUAL_REVIEW_BRANDS

BASE = "https://catalog.antiquorum.swiss"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}
EST_RE = re.compile(r"([A-Z]{3})\s*([\d,\.]+)\s*[-–]\s*([\d,\.]+)")

def _num(s):
    try:
        return float(s.replace(",", "").replace(".00", ""))
    except Exception:
        return None

def discover_auctions():
    r = requests.get(f"{BASE}/catalog", headers=HEADERS, timeout=30)
    r.raise_for_status()
    return sorted(set(re.findall(r"/en/auctions/([a-z0-9_]+)/lots", r.text)))

MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], 1)}

def _slug_status(slug: str) -> str:
    """Infer lot status from slug like 'monaco_june_2026' vs today (UTC)."""
    from datetime import datetime, timezone
    m = re.search(r"([a-z]+)_(\d{4})$", slug)
    if m and m.group(1) in MONTHS:
        y, mo = int(m.group(2)), MONTHS[m.group(1)]
        now = datetime.now(timezone.utc)
        if (y, mo) < (now.year, now.month):
            return "past"
    return "upcoming"

def fetch_auction(slug: str, max_pages: int = 30):
    status = _slug_status(slug)
    lots, seen = [], set()
    for page in range(1, max_pages + 1):
        url = f"{BASE}/en/auctions/{slug}/lots?page={page}"
        r = requests.get(url, headers=HEADERS, timeout=30)
        if r.status_code != 200:
            break
        soup = BeautifulSoup(r.text, "html.parser")
        anchors = [a for a in soup.select("a[href*='/en/lots/']")]
        page_new = 0
        for a in anchors:
            href = a.get("href", "")
            if not href or href in seen:
                continue
            seen.add(href)
            node, txt = a, ""
            for _ in range(5):
                node = node.parent
                if node is None:
                    break
                txt = node.get_text(" | ", strip=True)
                if EST_RE.search(txt) or len(txt) > 120:
                    break
            brand, kw = match_brand(txt or href)
            if not brand:
                continue
            m_lot = re.search(r"-lot-(\d+)-(\d+)$", href)
            lot_no = m_lot.group(2) if m_lot else ""
            est = EST_RE.search(txt)
            cur, lo, hi = (est.group(1), _num(est.group(2)), _num(est.group(3))) if est else ("EUR", None, None)
            img_el = node.find("img") if node else None
            img = (img_el.get("src") or img_el.get("data-src") or "") if img_el else ""
            title = " ".join(txt.split("|")[1:3]).strip()[:160] if "|" in txt else txt[:160]
            lots.append(Lot(
                lot_id=f"antiquorum_{slug}_{lot_no or href.rsplit('/', 1)[-1]}",
                platform="Antiquorum", platform_type="major_house",
                source_url=href if href.startswith("http") else BASE + href,
                auction_name=slug.replace("_", " ").title(),
                lot_number=lot_no, brand=brand, brand_matched_keyword=kw,
                title_raw=title, estimate_low=lo, estimate_high=hi,
                estimate_currency=cur, status=status,
                buyers_premium_pct=26.0,
                image_url=img,
                manual_review=brand in MANUAL_REVIEW_BRANDS,
            ))
            page_new += 1
        if not anchors:
            break
        time.sleep(1.5)  # polite delay
    return lots

def run():
    out = []
    try:
        slugs = discover_auctions()
    except Exception as e:
        print(f"[antiquorum] discovery failed: {e}")
        return out
    print(f"[antiquorum] auctions: {slugs}")
    for slug in slugs:
        try:
            lots = fetch_auction(slug)
            print(f"[antiquorum] {slug}: {len(lots)} whitelist lots")
            out += lots
        except Exception as e:
            print(f"[antiquorum] {slug} failed: {e}")
    return out
