"""Keep observation freshness separate from auction outcome."""
from copy import deepcopy
from adapters.item_filter import exclusion_reason

ACTIVE = {'upcoming', 'live'}
STATUSES = ACTIVE | {'past', 'unsold', 'withdrawn', 'ended', 'unknown'}


def active(lot):
    return lot.get('status') in ACTIVE and not lot.get('data_stale', False)


def normalize(lot):
    if lot.get('status') not in STATUSES:
        lot['status'] = 'unknown'
    # Old adapters use "past" for a finished sale, not necessarily a sale result.
    if lot['status'] == 'past' and not lot.get('sold_price') and lot.get('sale_result') != 'sold':
        lot['status'] = 'ended'
    if lot['status'] != 'past':
        lot['sold_price'] = None
        lot['sold_usd'] = None
    if not active(lot):
        lot['arb_flag'] = False
        lot['arb_margin_pct'] = None
    return lot


def preserve_missing(current, previous, health, now):
    """Missing from any source is not evidence of sale, withdrawal, or deletion.

    Keep old timestamps and old FX conversions intact; no re-scoring or alerts.
    A subsequent successful observation naturally replaces the carried record.
    """
    ids = {l['lot_id'] for l in current}
    states = {h['source']: h['state'] for h in health}
    counts = {}
    for lid, old in previous.items():
        if lid in ids or exclusion_reason(old.get('title_raw')):
            continue
        lot = normalize(deepcopy(old))
        source = lid.split('_', 1)[0]
        state = states.get(source, 'not_checked')
        lot.update(data_stale=True, is_new=False, arb_flag=False, arb_margin_pct=None,
                   stale_reason='source_failure' if state in {'failed','partial_or_failed','empty_or_failed'} else 'not_observed',
                   missing_since=old.get('missing_since') or now)
        current.append(lot)
        ids.add(lid)
        counts[source] = counts.get(source, 0) + 1
    for h in health:
        h['retained_stale'] = counts.get(h['source'], 0)
    return current


def merge_archive(archive, current):
    """Refresh known results and remove records explicitly corrected to non-sales."""
    by_id = {l['lot_id']: l for l in archive}
    for lot in current:
        if lot.get('data_stale'):
            continue
        if lot.get('status') == 'past' and lot.get('sold_usd'):
            by_id[lot['lot_id']] = lot
        elif lot.get('status') in {'unsold', 'withdrawn'}:
            by_id.pop(lot['lot_id'], None)
    return list(by_id.values())
