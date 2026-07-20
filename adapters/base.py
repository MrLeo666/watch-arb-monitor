# adapters/base.py — shared Lot model + brand whitelist matching
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Optional
import re

@dataclass
class Lot:
    """Normalized lot record shared across all platform adapters."""
    lot_id: str
    platform: str
    platform_type: str          # major_house | online | regional | aggregator
    source_url: str
    auction_name: str = ""
    auction_date: str = ""       # ISO 8601 (end date for timed sales)
    lot_number: str = ""
    brand: str = ""
    brand_matched_keyword: str = ""
    title_raw: str = ""
    estimate_low: Optional[float] = None
    estimate_high: Optional[float] = None
    estimate_currency: str = ""
    estimate_low_usd: Optional[float] = None
    estimate_high_usd: Optional[float] = None
    estimate_low_hkd: Optional[float] = None
    current_bid: Optional[float] = None      # live bid if platform exposes it (native ccy)
    sold_price: Optional[float] = None       # realized price for past lots (native ccy)
    status: str = "upcoming"                 # upcoming | live | past
    buyers_premium_pct: Optional[float] = None
    image_url: str = ""
    manual_review: bool = False              # brand ambiguity (e.g. Daniel Roth / Genta)
    fair_value_usd: Optional[float] = None
    fair_value_source: str = ""
    arb_margin_pct: Optional[float] = None
    arb_flag: bool = False
    first_seen: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_seen: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    is_new: bool = False

    def dict(self):
        return asdict(self)


# --- Brand whitelist with matching aliases (market-consensus independents) ---
# Short aliases (<= 7 chars) are matched with word boundaries to avoid false hits.
BRAND_ALIASES = {
    "F.P. Journe": ["f.p. journe", "fp journe", "f.p.journe", "f. p. journe", "journe"],
    "Patek Philippe": ["patek philippe", "patek"],
    "Cartier": ["cartier"],
    "Akrivia": ["akrivia", "rexhep rexhepi", "rexhepi", "chronometre contemporain",
                "chronomètre contemporain"],
    "Philippe Dufour": ["philippe dufour", "dufour"],
    "Kari Voutilainen": ["voutilainen", "vingt-8"],
    "De Bethune": ["de bethune", "db28", "db25"],
    "MB&F": ["mb&f", "mb & f", "legacy machine", "horological machine"],
    "Urwerk": ["urwerk"],
    "Simon Brette": ["simon brette"],
    "Roger W. Smith": ["roger w. smith", "roger smith"],
    "George Daniels": ["george daniels"],
    "Greubel Forsey": ["greubel forsey", "greubel"],
    "Laurent Ferrier": ["laurent ferrier"],
    "Grönefeld": ["grönefeld", "gronefeld"],
    "Petermann Bédat": ["petermann bédat", "petermann bedat", "petermann"],
    "Sylvain Pinaud": ["sylvain pinaud"],
    "Theo Auffret": ["theo auffret", "auffret"],
    "Raúl Pagès": ["raúl pagès", "raul pages"],
    "Christian Klings": ["christian klings"],
    "Vianney Halter": ["vianney halter"],
    "Romain Gauthier": ["romain gauthier"],
    "Urban Jürgensen": ["urban jürgensen", "urban jurgensen"],
    "Daniel Roth": ["daniel roth"],            # manual review: Bulgari reuse
    "Gérald Genta": ["gérald genta", "gerald genta"],  # manual review: Bulgari reuse
    "A. Lange & Söhne": ["a. lange", "lange & söhne", "lange & sohne", "lange und söhne",
                          "datograph", "zeitwerk", "pour le mérite", "pour le merite",
                          "double split", "triple split"],
}

MANUAL_REVIEW_BRANDS = {"Daniel Roth", "Gérald Genta"}

_WS = re.compile(r"\s+")

def _norm(text: str) -> str:
    return _WS.sub(" ", (text or "").lower()).strip()

def match_brand(title: str):
    """Return (brand, matched_keyword) or (None, None)."""
    t = _norm(title)
    if not t:
        return None, None
    for brand, aliases in BRAND_ALIASES.items():
        for kw in aliases:
            if len(kw) <= 7:
                if re.search(rf"(?<![a-z]){re.escape(kw)}(?![a-z])", t):
                    return brand, kw
            elif kw in t:
                return brand, kw
    return None, None
