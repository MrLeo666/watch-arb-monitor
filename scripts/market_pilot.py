"""Fetch opt-in sources into a separate report; never notify or alter production data."""
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters import bonhams, sothebys


def main():
    output = Path('research'); output.mkdir(exist_ok=True)
    report = {'checked_at':datetime.now(timezone.utc).isoformat(), 'sources':{}}
    lots = []
    for mod in (bonhams, sothebys):
        name = mod.__name__.split('.')[-1]
        try:
            records = mod.run()
            lots.extend(l.dict() for l in records)
            report['sources'][name] = mod.LAST_REPORT
            print(name, len(records), 'retained watch lots', flush=True)
        except Exception as e:
            report['sources'][name] = {'errors':[{'error':str(e)}]}
    # Explicit historic sample validates pagination and hammer-price interpretation.
    try:
        records, sample = bonhams.fetch_sale('https://www.bonhams.com/auction/31990/weekly-watches/')
        lots.extend(l.dict() for l in records)
        report['historical_sample'] = sample
    except Exception as e:
        report['historical_sample'] = {'error': str(e)}
    report['counts'] = {name:sum(l['platform']==name for l in lots) for name in ('Bonhams', "Sotheby's")}
    (output/'market-pilot.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    (output/'market-pilot-lots.json').write_text(json.dumps(lots,ensure_ascii=False,indent=2))
    preview = output/'preview'; preview.mkdir(exist_ok=True)
    for name in ('index.html','decision.js'):
        shutil.copy2(Path('docs')/name, preview/name)
    page = (preview/'index.html').read_text()
    page = page.replace('<body>', '<body><p style="padding:16px;background:#493d20">市場試接小樣：Sotheby’s 已核對逐場分頁總數；Bonhams 含歷史成交對照。未驗證即時出價與佣金，不提供套利訊號。這不是正式站資料。</p>')
    (preview/'index.html').write_text(page)
    (preview/'lots.json').write_text(json.dumps(lots,ensure_ascii=False,indent=1))
    (preview/'meta.json').write_text(json.dumps({'updated_at':report['checked_at'], 'counts':report['counts']}))

if __name__ == '__main__':
    main()
