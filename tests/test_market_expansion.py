import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from adapters import bonhams, bukowskis
from scripts.refresh_markets import refresh

HTML = (Path(__file__).parent/'fixtures/bukowskis.html').read_text()
NOW = datetime(2026,9,25,tzinfo=timezone.utc)

class ExpansionTests(unittest.TestCase):
    def test_watches_only_real_bid_and_exact_end(self):
        lots, ids, count, pages = bukowskis.parse_page(HTML,NOW)
        self.assertEqual(len(ids),count)
        self.assertGreater(count,len(lots)) # excludes Patek straps
        lot = next(l for l in lots if l.lot_number=='1725816')
        self.assertEqual((lot.current_bid,lot.estimate_low,lot.estimate_currency),(14000,15000,'SEK'))
        self.assertEqual(lot.ends_at,'2026-09-27T17:56:00+00:00')
        self.assertTrue(all(l.status=='live' and not l.scoring_enabled for l in lots))
        self.assertTrue(all('wristwatch' in l.title_raw.lower() for l in lots))

    def test_ended_bid_is_not_sale(self):
        lots,*_=bukowskis.parse_page(HTML,datetime(2027,1,1,tzinfo=timezone.utc))
        self.assertTrue(all(l.status=='ended' and l.current_bid is None and l.sold_price is None for l in lots))

    def test_unknown_caption_does_not_become_bid(self):
        lots,*_=bukowskis.parse_page(HTML.replace('Current bid','Starting bid'),NOW)
        self.assertTrue(all(l.current_bid is None and l.status=='unknown' for l in lots))

    def test_incomplete_and_blocked_catalogue_fail(self):
        with self.assertRaises(ValueError):bukowskis.parse_page('<html>Forbidden</html>')
        wrong=HTML.replace(' items</span>','0 items</span>',1)
        with patch('adapters.bukowskis.fetch',return_value=wrong):
            with self.assertRaisesRegex(ValueError,'Incomplete'):bukowskis.run()

    def test_bonhams_department_failure_still_rechecks_known_sales(self):
        with patch('adapters.bonhams.fetch',side_effect=RuntimeError('403 Forbidden')),patch('adapters.bonhams.known_sales',return_value=['https://www.bonhams.com/auction/31990/']),patch('adapters.bonhams.fetch_sale',return_value=(['lot'],{'complete':True})):
            self.assertEqual(bonhams.run(),['lot'])
            self.assertEqual(len(bonhams.LAST_REPORT['errors']),1)

    def test_bonhams_open_bidding_is_live_without_invented_bid(self):
        fixture=json.loads((Path(__file__).parent/'fixtures/bonhams.json').read_text())
        record=fixture['records'][0]
        record.update(status='NEW',auctionStatus='READY',flags={'isAuctionEnded':False},auctionBiddingStatus='IP',biddableFrom={'timestamp':0},auctionEndDate={'timestamp':4102444800})
        lot=bonhams.parse_record(record,fixture['auction'])
        self.assertEqual(lot.status,'live')
        self.assertIsNone(lot.current_bid)
        self.assertIsNone(lot.sold_price)

    def test_bonhams_short_url_uses_canonical_pagination(self):
        fixture=json.loads((Path(__file__).parent/'fixtures/bonhams.json').read_text())
        auction=dict(fixture['auction'],iSaleNo=31990,slug='weekly-watches')
        def page(record):
            return '<script id="__NEXT_DATA__">'+json.dumps({'props':{'pageProps':{'auction':auction,'lotData':{'nbHits':2,'auctionLots':[record]}}}})+'</script>'
        with patch('adapters.bonhams.fetch',side_effect=[page(fixture['records'][0]),page(fixture['records'][1])]) as get, patch('adapters.bonhams.time.sleep'):
            lots,report=bonhams.fetch_sale('https://www.bonhams.com/auction/31990/')
            self.assertEqual(get.call_args.args[0],'https://www.bonhams.com/auction/31990/weekly-watches/?page=2')
            self.assertEqual(len(lots),2)
            self.assertTrue(report['complete'])

    def test_known_sales_deduplicated_and_external_links_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'lots.json'
            p.write_text(json.dumps([{'platform':'Bonhams','source_url':u} for u in ['https://www.bonhams.com/auction/123/lot/1/','https://www.bonhams.com/auction/123/lot/2/','https://evil.com/auction/124/']]))
            self.assertEqual(bonhams.known_sales(p),['https://www.bonhams.com/auction/123/'])

    def test_partial_refresh_preserves_other_sources_and_full_timestamp(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d); old=[{'lot_id':'other_1','status':'live','last_seen':'old'},{'lot_id':'bonhams_1','status':'live','last_seen':'old'}]
            (p/'lots.json').write_text(json.dumps(old));(p/'meta.json').write_text(json.dumps({'updated_at':'full','sources':[]}))
            with patch('adapters.bonhams.run',side_effect=RuntimeError('403')):
                meta=refresh(['bonhams'],p)
            out=json.loads((p/'lots.json').read_text())
            self.assertEqual(out[0],old[0]);self.assertEqual(meta['updated_at'],'full')
            self.assertTrue(out[1]['data_stale']);self.assertEqual(out[1]['last_seen'],'old')
