import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from scripts.refresh_price_history import parse_chart, summarize, refresh


def page(points):
    return '<div data-chart-init-code-function-name="chart"><script>function chart() { return (' + json.dumps(points) + '); }</script></div>'


class PriceHistoryTests(unittest.TestCase):
    def test_chart_only_not_retail_or_gated_results(self):
        html = page([[1609459200000, 1000], [1640995200000, 3000]])
        html += '<div>Sold: 99999 Log in to consult the next results</div>'
        self.assertEqual(len(parse_chart(html)[0]), 2)

    def test_retain_duplicate_points_and_low_positive_outliers(self):
        points, excluded = parse_chart(page([[1609459200000, 5], [1609459200000, 5], [1609459200000, 0]]))
        self.assertEqual(len(points), 2)
        self.assertEqual(excluded, 1)

    def test_schema_failures_are_not_zero_history(self):
        for html in ['<html>log in</html>', page([]), page([[1, '2000']]), page([[1, True]]), page([[1, -4]])]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_chart(html)

    def test_median_not_mean_and_years_not_interpolated(self):
        rows = summarize([[1609459200000, 1000], [1609459200000, 2000], [1609459200000, 999999], [1672531200000, 4000]])
        self.assertEqual([r['year'] for r in rows], [2021, 2023])
        self.assertEqual(rows[0]['median'], 2000)
        self.assertEqual(rows[0]['count'], 3)

    @patch('scripts.refresh_price_history.time.sleep')
    @patch('scripts.refresh_price_history.requests.Session')
    def test_failure_preserves_snapshot_and_sets_stale(self, session, sleep):
        url='https://www.collectorsquare.com/en/watches/patek-philippe/nautilus/lpi'
        session.return_value.get.return_value = Mock(url=url, text='<html>missing chart</html>')
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'history.json'
            p.write_text(json.dumps({'series':[{'source_url':url,'points':[[1,123]],'retrieved_at':'2020-01-01','state':'ok'}]}))
            count,errors=refresh(p,Path(folder)/'cache',1)
            row=json.loads(p.read_text())['series'][0]
            self.assertEqual(count,0)
            self.assertEqual(len(errors),1)
            self.assertEqual(row['points'],[[1,123]])
            self.assertEqual(row['retrieved_at'],'2020-01-01')
            self.assertEqual(row['state'],'stale')

    def test_checked_in_series_are_isolated_from_scoring(self):
        path=Path('docs/price_history.json')
        if not path.exists(): self.skipTest('No local history snapshot')
        data=json.loads(path.read_text())
        self.assertEqual(len({s['source_url'] for s in data['series']}),len(data['series']))
        for s in data['series']:
            self.assertFalse(s['scoring_enabled'])
            self.assertEqual(s['independent_source_count'],1)
            self.assertEqual(s['currency'],'EUR')
            self.assertEqual(s['annual'],summarize(s['points']))
