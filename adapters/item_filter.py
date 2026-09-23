"""Conservative title-based exclusion of standalone accessories/non-watch lots.

Do not reject complete watches merely because box, papers, strap or bracelet
appear in their descriptions. Ambiguous titles remain for manual review.
"""
import re

# Catalogues commonly separate the object heading and description by 2+ spaces.
_ACCESSORY = re.compile(
    r'\b(?:accessor(?:y|ies)|presentation\s+box(?:es)?|(?:wrist)?watch\s+box(?:es)?|'
    r'(?:electronic\s+)?winding\s+box|watch\s+wind(?:er|ing)|horological\s+(?:book|tools?)|push\s+pins?|'
    r'vip\s+gifts?|exclusive\s+gifts?|vide[- ]poche|cardholder|display\s+stands?|'
    r'backpacks?|rucksacks?|handbags?|(?:tote|duffel|travel|shoulder)\s+bags?|luggage|wallets?|'
    r'deployant\s+clasp|(?:table|desk|wall|travel)\s+clock)\b', re.I)
_WATCH = re.compile(
    r'\b(?:montre|montres|wristwatch|wristwatc|pocket\s+watch|chronograph|chronometer|'
    r'automatic|quartz|manual[ -]wind(?:ing)?|perpetual\s+calendar)\b', re.I)
_GENERIC = re.compile(r'\b(?:box(?:es)?|straps?|bracelets?|buckles?|clasps?|'
                      r'certificates?|papers|catalogues?|books?|pouches|dials?|'
                      r'scarves|scarf|towels?|pens?|cufflinks?)\b', re.I)
_MODEL = re.compile(r'\b(?:tank|santos|aquanaut|nautilus|calatrava|panth[eè]re|'
                    r'pasha|souverain|datograph|zeitwerk|tourbillon)\b', re.I)


def exclusion_reason(title):
    """Return an exclusion reason or None; never uses price as a proxy."""
    title = title or ''
    heading = re.split(r'\s{2,}', title)[0]
    # Accessory descriptions after 'with'/'accompanied by' are not the lot itself.
    subject = re.split(r'\b(?:with|including|accompanied by|complete with)\b', heading, flags=re.I)[0]
    match = _ACCESSORY.search(subject)
    if match:
        # A complete wristwatch with additional accessories must remain.
        prefix = subject[:match.start()]
        if _WATCH.search(prefix):
            return None
        return 'standalone accessory or non-watch: ' + match.group(0).lower()
    # Generic nouns alone are too broad: watch models and movement descriptions
    # protect legitimate "Tank ... Bracelet" and "Box and Papers" listings.
    if _GENERIC.search(subject) and not _WATCH.search(title) and not _MODEL.search(subject):
        if '/' in subject:  # structured model/material/strap titles need review
            return None
        return 'standalone accessory: ' + _GENERIC.search(subject).group(0).lower()
    return None
