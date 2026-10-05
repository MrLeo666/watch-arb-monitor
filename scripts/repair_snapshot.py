"""Recover missing records without claiming a new scrape or sending notifications.

Usage: python scripts/repair_snapshot.py /path/to/previous-lots.json [fresh-lots.json]
Fresh observations must come from the adapter, never from an old saved snapshot.
"""
import json
import sys
from pathlib import Path
from datetime import datetime, timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lifecycle import normalize, preserve_missing, active
from adapters.item_filter import exclusion_reason


def main():
    previous=json.loads(Path(sys.argv[1]).read_text())
    current=json.loads(Path('docs/lots.json').read_text())
    meta=json.loads(Path('docs/meta.json').read_text())
    rows={l['lot_id']:normalize(l) for l in current if not exclusion_reason(l.get('title_raw'))}
    if len(sys.argv)>2:
        for l in json.loads(Path(sys.argv[2]).read_text()):
            if exclusion_reason(l.get('title_raw')):continue
            old=rows.get(l['lot_id']) or next((v for v in previous if v['lot_id']==l['lot_id']),{})
            l['first_seen']=old.get('first_seen',l.get('first_seen'))
            l['is_new']=not bool(old)
            rows[l['lot_id']]=normalize(l)
    now=datetime.now(timezone.utc).isoformat()
    out=preserve_missing(list(rows.values()),{l['lot_id']:l for l in previous},meta.get('sources',[]),now)
    # Keep the last full-build timestamp. A repair isn't a successful full scrape.
    meta['repaired_at']=now
    meta['counts']={'total':len(out),'active':sum(active(l) for l in out),
                    'new':sum(bool(l.get('is_new')) and active(l) for l in out),
                    'stale':sum(bool(l.get('data_stale')) for l in out)}
    Path('docs/lots.json').write_text(json.dumps(out,ensure_ascii=False,indent=1))
    Path('docs/meta.json').write_text(json.dumps(meta,ensure_ascii=False))
    print(meta['counts'])

if __name__=='__main__':main()
