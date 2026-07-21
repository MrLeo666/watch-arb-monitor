# c24.py — Chrono24 lowest-ask lookup by reference number. VERIFIED 2026-07:
# /search/index.htm serves ld+json with listing prices (currencyId=USD honored);
# per-reference pages are bot-blocked but search is not.
# Method: query the lot's reference number, take a robust low (2nd-lowest when
# >=4 listings), require >=3 listings. Ask prices carry negotiation margin, so
# net dealer-channel proceeds are modeled as low_ask * 0.85 in build.py.
# Cache: docs/c24_cache.json, 7-day TTL, keyed by normalized reference.
import json
import os
import re
import time
import requests

CACHE_PATH = "docs/c24_cache.json"
TTL_DAYS = 7
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
           "Accept-Language": "en"}
REF_RE = re.compile(r"Ref\.?\s*([A-Za-z0-9][A-Za-z0-9\./\-]{2,20})")

def extract_ref(title: str):
    m = REF_RE.search(title or "")
    if not m:
        return None
    ref = m.group(1).strip(".-/")
    # discard pure short numbers likely to be sizes/years
    if re.fullmatch(r"\d{1,3}", ref):
        return None
    return ref

def _load_cache():
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def _save_cache(c):
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(c, f, ensure_ascii=False)

def _query(ref: str):
    url = ("https://www.chrono24.com/search/index.htm"
           f"?query={requests.utils.quote(ref)}&dosearch=true&currencyId=USD")
    r = requests.get(url, headers=HEADERS, timeout=30)
    if r.status_code != 200:
        return None
    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', r.text, re.S)
    prices = []
    for b in blocks:
        prices += [float(p) for p in re.findall(r'"price":\s*"?([\d\.]+)"?', b)]
    prices = sorted(p for p in prices if p >= 500)  # drop straps/accessory noise
    if len(prices) < 3:
        return None
    low = prices[1] if len(prices) >= 4 else prices[0]  # robust low
    return {"low": round(low), "n": len(prices)}

def lookup(ref: str, cache: dict):
    key = ref.upper()
    now = time.time()
    hit = cache.get(key)
    if hit and now - hit.get("ts", 0) < TTL_DAYS * 86400:
        return hit.get("data")
    data = None
    try:
        data = _query(ref)
    except Exception as e:
        print(f"[c24] {ref} failed: {e}")
    cache[key] = {"ts": now, "data": data}
    time.sleep(1.5)  # polite delay between live queries
    return data

def enrich(lots: list, max_queries: int = 60):
    """Attach c24_low_usd / c24_count to active lots that carry a reference
    number. Live queries capped per run; cache covers the rest over days."""
    cache = _load_cache()
    queries = 0
    enriched = 0
    for lot in lots:
        if lot.get("status") == "past":
            continue
        ref = extract_ref(lot.get("title_raw", ""))
        if not ref:
            continue
        key = ref.upper()
        cached = cache.get(key)
        fresh = cached and time.time() - cached.get("ts", 0) < TTL_DAYS * 86400
        if not fresh:
            if queries >= max_queries:
                continue
            queries += 1
        data = lookup(ref, cache)
        if data:
            lot["c24_low_usd"] = data["low"]
            lot["c24_count"] = data["n"]
            enriched += 1
    _save_cache(cache)
    print(f"[c24] {enriched} lots priced ({queries} live queries)")
    return lots
