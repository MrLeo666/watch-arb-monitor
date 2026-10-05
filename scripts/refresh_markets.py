"""Refresh only the selected pilots locally, without notifications or publication.

Usage: python scripts/refresh_markets.py bonhams bukowskis
This is also the manual alternative when a cloud runner receives HTTP 403.
"""
import importlib
import json
import sys
from pathlib import Path
from datetime import datetime, timezone
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lifecycle import normalize, preserve_missing, active
from adapters.item_filter import exclusion_reason


def refresh(names, directory=ROOT/'docs'):
    if not names or set(names) - {'bonhams', 'bukowskis', 'sothebys'}:
        raise ValueError('Select bonhams, bukowskis and/or sothebys')
    directory = Path(directory)
    old = json.loads((directory/'lots.json').read_text())
    meta = json.loads((directory/'meta.json').read_text())
    rows = {l['lot_id']:l for l in old}
    for name in dict.fromkeys(names):
        mod = importlib.import_module('adapters.'+name)
        now = datetime.now(timezone.utc).isoformat()
        try:
            found = mod.run()
            report = mod.LAST_REPORT
            state = ('partial_or_failed' if found else 'failed') if report.get('errors') else ('returned' if found else 'no_matches')
        except Exception as e:
            found = []; state = 'failed'
            report = dict(getattr(mod, 'LAST_REPORT', {}))
            report['errors'] = report.get('errors', []) + [{'error': str(e)}]
        health = {'source':name,'state':state,'count':len(found),'checked_at':now,'coverage':report}
        prior = {k:v for k,v in rows.items() if k.startswith(name+'_')}
        fresh = []
        for obj in found:
            lot = normalize(obj.dict())
            if exclusion_reason(lot.get('title_raw')): continue
            previous = prior.get(lot['lot_id'], {})
            lot['first_seen'] = previous.get('first_seen',lot['first_seen'])
            lot['is_new'] = not bool(previous)
            fresh.append(lot)
        fresh_count = len(fresh)
        updated = preserve_missing(fresh, prior, [health], now)
        for k in prior: rows.pop(k)
        rows.update({l['lot_id']:l for l in updated})
        meta['sources'] = [h for h in meta.get('sources',[]) if h['source'] != name] + [health]
        print(name, state, 'fresh:',fresh_count, 'retained stale:',health.get('retained_stale',0))
    out = list(rows.values())
    meta['partial_updated_at'] = datetime.now(timezone.utc).isoformat()
    meta['counts'] = {'total':len(out),'active':sum(active(l) for l in out),
        'new':sum(active(l) and bool(l.get('is_new')) for l in out),'stale':sum(bool(l.get('data_stale')) for l in out)}
    # The full-build timestamp and unrelated sources' observations stay unchanged.
    (directory/'lots.json').write_text(json.dumps(out,ensure_ascii=False,indent=1))
    (directory/'meta.json').write_text(json.dumps(meta,ensure_ascii=False))
    return meta

if __name__ == '__main__': refresh(sys.argv[1:])
