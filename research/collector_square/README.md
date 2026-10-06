# Collector Square integration verification — 2026-10-05

Source: https://www.collectorsquare.com/en/luxprice-index-watch.html

Verified live public collection and reference-family pages, with 10 successful
chart imports. The chart is a scatter series of millisecond timestamps and prices,
not a ready-made annual index. Local annual medians are calculated from these points.
The public `front-lpiresults.js` asset's tooltip says `eur`; its y-axis says `k €`.
This verifies chart currency only, not the FX conversion method or fee inclusion.

The page's chart count differs from its advertised auction-results count.
It also has retail offers and result rows whose continuation requires login.
The importer reads only the function named by the public chart widget and never
reads those result rows, retail listings, login routes or continuation endpoints.
Do not describe this as a complete database import. Original source HTML is local
in `tmp/collector_square`, identified by URL hash; output retains a content hash.

Nautilus has mixed references; the 5711 reference family includes Tiffany and
other variants. Therefore chart points do not constitute matched comparables.
No scoring connection exists. Several series' latest observations are in 2024,
whereas Pasha includes 2025. Fetch date must never masquerade as sale date.
Chart dates are UTC timestamps; source local calendar dates can differ by a day.
No manual adjustment is made without a verified source timezone.

Implementation: independent JSON snapshot, history page, bounded manual updater,
radar research links, and offline regression checks. No automatic job or deployment
was added. Pages are a research reference, not independently verified price advice.
