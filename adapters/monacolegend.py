# adapters/monacolegend.py — VERIFIED 2026-07: server-rendered (Laravel/Livewire)
# with semantic classes: .lot-number / .lot-brand / .lot-title / .lot-estimation.
# Estimates in Swiss format "Fr. 25'000 – 50'000" (Fr. = CHF) or "€ 10'000 – 20'000".
# Auction discovery: homepage links /auction/{slug}. Lot URL: /auction/{slug}/lot-N.
import re
import time
import requests
from bs4 import BeautifulSoup
from .base import Lot, match_brand, MANUAL_REVIEW_BRANDS

BASE = "https://www.monacolegendauctions.com"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}
EST_RE = re.compile(r"(Fr\.|€|EUR|CHF|\$)\s*([\d'’,]+)\s*[–\-‒—]\s*([\d'’,]+)")
CUR_MAP = {"Fr.": "CHF", "€": "EUR", "$": "USD"}

def _num(s):
    try:
        return float(re.sub(r"[',’]", "", s))
    except Exception:
        return None

def discover_auctions():
    r = requests.get(BASE + "/", headers=HEADERS, timeout=30)
    r.raise_for_status()
    slugs = sorted(set(re.findall(r'href="(?:https://www\.monacolegendauctions\.com)?/?auction/([a-z0-9\-]+)"', r.text)))
    return [s for s in slugs if s and s != "auction"]

def fetch_auction(slug: str):
    r = requests.get(f"{BASE}/auction/{slug}", headers=HEADERS, timeout=40)
    if r.status_code != 200:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    is_past = "results" in r.text.lower() and "_results.pdf" in r.text
    lots = []
    for det in soup.select("div.lot-detail"):
        head = det.select_one("h3.lot-header")
        if not head:
            continue
        num_el = head.select_one(".lot-number")
        brand_el = head.select_one(".lot-brand")
        title_el = head.select_one(".lot-title")
        lot_no = num_el.get_text(strip=True) if num_el else ""
        brand_txt = brand_el.get_text(strip=True) if brand_el else ""
        title_txt = title_el.get_text(strip=True) if title_el else ""
        full = f"{brand_txt} {title_txt}"
        brand, kw = match_brand(full)
        if not brand:
            continue
        est_el = det.select_one(".lot-estimation")
        est = EST_RE.search(est_el.get_text(" ", strip=True)) if est_el else None
        cur, lo, hi = ("", None, None)
        if est:
            cur = CUR_MAP.get(est.group(1), est.group(1))
            lo, hi = _num(est.group(2)), _num(est.group(3))
        a = det.find("a", href=True)
        href = a["href"] if a else f"{BASE}/auction/{slug}/lot-{lot_no}"
        # image lives in sibling <figure>; search the card's parent
        img = ""
        parent = det.parent
        if parent:
            im = parent.find("img")
            if im:
                img = (im.get("src") or (im.get("srcset") or "").split(" ")[0] or "")
        lots.append(Lot(
            lot_id=f"monacolegend_{slug}_{lot_no}",
            platform="Monaco Legend", platform_type="major_house",
            source_url=href if href.startswith("http") else BASE + href,
            auction_name=slug.replace("-", " ").title(),
            lot_number=lot_no,
            brand=brand, brand_matched_keyword=kw,
            title_raw=f"{brand_txt} {title_txt}"[:160],
            estimate_low=lo, estimate_high=hi, estimate_currency=cur,
            status="past" if is_past else "upcoming",
            buyers_premium_pct=25.0,  # approximate; verify per sale
            image_url=img,
            manual_review=brand in MANUAL_REVIEW_BRANDS,
        ))
    return lots

def run():
    out = []
    try:
        slugs = discover_auctions()
    except Exception as e:
        print(f"[monacolegend] discovery failed: {e}")
        return out
    print(f"[monacolegend] auctions: {slugs}")
    for slug in slugs:
        try:
            lots = fetch_auction(slug)
            print(f"[monacolegend] {slug}: {len(lots)} whitelist lots")
            out += lots
        except Exception as e:
            print(f"[monacolegend] {slug} failed: {e}")
        time.sleep(2)
    return out
