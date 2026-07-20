# comps.py — internal comparables engine.
# Derives fair_value_usd for active lots from our own realized-price archive
# (past lots with sold_price). Honest limitations: no condition/size/box-papers
# adjustment; requires >=2 comps; matches on model tokens after stripping noise.
import re
from statistics import median

STOP = {
    "a", "an", "the", "and", "with", "for", "of", "in", "ref", "reference",
    "watch", "wristwatch", "switzerland", "swiss", "geneva", "geneve",
    "steel", "stainless", "gold", "yellow", "white", "rose", "pink", "platinum",
    "titanium", "18k", "mm", "dial", "bracelet", "strap", "case", "self",
    "winding", "automatic", "manual", "fine", "rare", "very", "important",
    "lady", "ladies", "mens", "gentleman", "no", "movement", "certificate",
    "box", "papers", "extract", "archives",
}

def tokens(title: str, brand: str) -> set:
    t = (title or "").lower()
    b = (brand or "").lower()
    for w in re.split(r"[^a-z0-9]+", b):
        if w:
            t = t.replace(w, " ")
    toks = set()
    for w in re.split(r"[^a-z0-9\.]+", t):
        w = w.strip(".")
        if len(w) < 2 or w in STOP:
            continue
        toks.add(w)
    return toks

def build_index(lots):
    """Index past lots with realized USD prices by brand."""
    idx = {}
    for l in lots:
        if l.get("status") != "past" or not l.get("sold_usd"):
            continue
        idx.setdefault(l["brand"], []).append((tokens(l["title_raw"], l["brand"]), l["sold_usd"]))
    return idx

def fair_value(lot, idx, min_comps=2, min_overlap=2):
    """Return (fair_value_usd, n_comps) or (None, 0).
    Conservative: needs >=2 shared model tokens (e.g. 'datograph' + 'perpetual',
    or a reference number + model word); uses only the best-overlap tier of
    comps; trims outliers beyond 3x/0.33x of the tier median."""
    pool = idx.get(lot["brand"]) or []
    if not pool:
        return None, 0
    lt = tokens(lot.get("title_raw", ""), lot["brand"])
    if not lt:
        return None, 0
    scored = []
    for ptoks, price in pool:
        n = len(lt & ptoks)
        if n >= min_overlap:
            scored.append((n, price))
    if len(scored) < min_comps:
        return None, 0
    best = max(n for n, _ in scored)
    tier = [p for n, p in scored if n == best]
    if len(tier) < min_comps:
        tier = [p for n, p in scored if n >= max(min_overlap, best - 1)]
    if len(tier) < min_comps:
        return None, 0
    m = median(tier)
    trimmed = [p for p in tier if m / 3 <= p <= m * 3] or tier
    if len(trimmed) < min_comps:
        return None, 0
    # dispersion guard: comps disagreeing >4x among themselves = unreliable match
    if max(trimmed) / max(min(trimmed), 1) > 4:
        return None, 0
    fv = round(median(trimmed), 0)
    # plausibility guard: >8x gap vs the lot's own price context is almost
    # always a model-mismatch (trophy comp vs standard piece), not arbitrage
    basis = lot.get("current_bid_usd") or lot.get("estimate_low_usd")
    if basis and (fv > basis * 8 or fv < basis / 8):
        return None, 0
    return fv, len(trimmed)
