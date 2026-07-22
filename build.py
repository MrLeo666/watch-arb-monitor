# build.py — orchestrate adapters, normalize FX, score arbitrage, detect new lots, notify.
import json
import os
from datetime import datetime, timezone

import requests

from adapters import phillips, loupethis, bezel, antiquorum, watchcollecting, monacolegend, allu
import comps
import c24
from adapters.base import Lot  # noqa: F401

OUT_PATH = "docs/lots.json"
ARCHIVE_PATH = "docs/archive.json"
META_PATH = "docs/meta.json"

# --- FX: fetch live rates with static fallback ---
FX_FALLBACK = {"USD": 1.0, "CHF": 1.13, "EUR": 1.08, "GBP": 1.27, "HKD": 0.128,
               "JPY": 0.0067, "CNY": 0.138, "SGD": 0.74, "SEK": 0.095, "DKK": 0.145}
USD_TO_HKD_FALLBACK = 7.8

def get_fx():
    try:
        r = requests.get("https://open.er-api.com/v6/latest/USD", timeout=15)
        rates = r.json()["rates"]
        to_usd = {c: (1.0 / v) for c, v in rates.items() if v}
        to_usd["USD"] = 1.0
        return to_usd, rates.get("HKD", USD_TO_HKD_FALLBACK)
    except Exception as e:
        print(f"[fx] live rates failed ({e}); using fallback")
        return FX_FALLBACK, USD_TO_HKD_FALLBACK

# --- Cost model (watches, 2026 rate cards; conservative simplifications) ---
BUYER_PREMIUM_DEFAULT = 0.25
SELLER_COST = 0.12        # consign to a major: negotiable 0-15%; conservative
SHIP_INSURE = 0.03        # ship + insure to HK
FX_COST = 0.015           # payment/FX friction
ARB_THRESHOLD = 0.25      # flag when expected margin >= 25%

def score(lot: dict, to_usd, usd_hkd):
    cur = lot.get("estimate_currency") or "USD"
    rate = to_usd.get(cur, 1.0)
    for k_src, k_dst in (("estimate_low", "estimate_low_usd"),
                         ("estimate_high", "estimate_high_usd")):
        v = lot.get(k_src)
        lot[k_dst] = round(v * rate, 2) if v is not None else None
    if lot.get("estimate_low_usd") is not None:
        lot["estimate_low_hkd"] = round(lot["estimate_low_usd"] * usd_hkd)
    if lot.get("sold_price") is not None:
        lot["sold_usd"] = round(lot["sold_price"] * rate, 2)
    if lot.get("current_bid") is not None:
        lot["current_bid_usd"] = round(lot["current_bid"] * rate, 2)
    # Basis for landed cost: live bid if present, else low estimate
    bid = lot.get("current_bid")
    basis = (bid * rate) if bid is not None else lot.get("estimate_low_usd")
    fv = lot.get("fair_value_usd")
    if fv and basis:
        bp = (lot.get("buyers_premium_pct") or BUYER_PREMIUM_DEFAULT * 100) / 100.0
        landed = basis * (1 + bp + SHIP_INSURE + FX_COST)  # HK import duty = 0%
        net_proceeds = fv * (1 - SELLER_COST)
        margin = (net_proceeds - landed) / landed
        lot["arb_margin_pct"] = round(margin * 100, 1)
        lot["arb_flag"] = margin >= ARB_THRESHOLD
    return lot

def enrich_fair_value(lot: dict):
    """Optional: WatchCharts API lookup (internal-use licence). Set WATCHCHARTS_API_KEY.
    Left as a stub until subscription is active; margin scoring activates automatically
    once fair_value_usd is populated."""
    key = os.environ.get("WATCHCHARTS_API_KEY")
    if not key:
        return lot
    # TODO: two-step lookup: /v3/search/watch -> uuid, then price endpoint (1 req/s).
    return lot

def load_previous():
    if os.path.exists(OUT_PATH):
        try:
            with open(OUT_PATH, encoding="utf-8") as f:
                return {l["lot_id"]: l for l in json.load(f)}
        except Exception:
            return {}
    return {}

def notify(lots):
    token, chat = os.environ.get("TG_TOKEN"), os.environ.get("TG_CHAT")
    if not (token and chat and lots):
        return
    for l in lots[:20]:
        est = ""
        if l.get("estimate_low"):
            est = f"估價 {l['estimate_currency']} {l['estimate_low']:,.0f}–{l['estimate_high'] or 0:,.0f}\n"
        bid = f"現時出價 USD {l['current_bid']:,.0f}\n" if l.get("current_bid") else ""
        msg = (f"🆕 {l['brand']} @ {l['platform']}\n{l['title_raw']}\n{est}{bid}"
               f"結標 {l.get('auction_date','')}\n{l['source_url']}")
        try:
            requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          data={"chat_id": chat, "text": msg}, timeout=15)
        except Exception as e:
            print(f"[notify] failed: {e}")

def main():
    prev = load_previous()
    to_usd, usd_hkd = get_fx()

    raw = []
    for mod in (phillips, loupethis, bezel, antiquorum, watchcollecting, monacolegend, allu):
        try:
            raw += mod.run()
        except Exception as e:
            print(f"[{mod.__name__}] adapter crashed: {e}")

    now = datetime.now(timezone.utc).isoformat()
    out, new_lots = [], []
    for lot_obj in raw:
        lot = lot_obj.dict()
        lot = enrich_fair_value(lot)
        lot = score(lot, to_usd, usd_hkd)
        old = prev.get(lot["lot_id"])
        if old:
            lot["first_seen"] = old.get("first_seen", now)
            lot["is_new"] = False
        else:
            lot["is_new"] = True
            if lot["status"] != "past":
                new_lots.append(lot)
        lot["last_seen"] = now
        out.append(lot)

    # Archive persistence: past lots that dropped off source listings are kept
    # forever in archive.json — the comps engine compounds over time.
    archive = []
    if os.path.exists(ARCHIVE_PATH):
        try:
            with open(ARCHIVE_PATH, encoding="utf-8") as f:
                archive = json.load(f)
        except Exception:
            archive = []
    known = {l["lot_id"] for l in out}
    arch_ids = {l["lot_id"] for l in archive}
    for lid, old in prev.items():
        if lid not in known and lid not in arch_ids and old.get("sold_usd"):
            archive.append(old)
    for l in out:
        if l["status"] == "past" and l.get("sold_usd") and l["lot_id"] not in arch_ids:
            archive.append(l)
            arch_ids.add(l["lot_id"])
    with open(ARCHIVE_PATH, "w", encoding="utf-8") as f:
        json.dump(archive, f, ensure_ascii=False)
    print(f"[archive] {len(archive)} realized lots banked")

    # Internal comparables: derive fair value from realized archive (compounding)
    idx = comps.build_index(archive)
    enriched = 0
    for lot in out:
        if lot["status"] == "past" or lot.get("fair_value_usd"):
            continue
        fv, n = comps.fair_value(lot, idx)
        if fv:
            lot["fair_value_usd"] = fv
            lot["fair_value_source"] = f"comps({n})"
            score(lot, to_usd, usd_hkd)  # idempotent; now computes margin
            enriched += 1
    print(f"[comps] fair value assigned to {enriched} active lots")

    # Chrono24 lowest-ask by reference number (precise match). When available,
    # margin uses conservative dealer-channel net: c24_low * 0.85, replacing
    # the token-matched comps basis for that lot.
    c24.enrich(out)
    for lot in out:
        if lot.get("c24_low_usd") and lot["status"] != "past":
            lot["fair_value_usd"] = round(lot["c24_low_usd"] * 0.85)
            lot["fair_value_source"] = f"C24({lot.get('c24_count')})"
            score(lot, to_usd, usd_hkd)

    # sort: live/upcoming first by date, then past
    out.sort(key=lambda l: (l["status"] == "past", l.get("auction_date") or "9999"))

    os.makedirs("docs", exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump({"updated_at": now,
                   "counts": {"total": len(out),
                              "new": len(new_lots),
                              "active": sum(1 for l in out if l["status"] != "past")}},
                  f, ensure_ascii=False)
    print(f"[build] {len(out)} lots ({len(new_lots)} new active) -> {OUT_PATH}")
    notify(new_lots)

if __name__ == "__main__":
    main()
