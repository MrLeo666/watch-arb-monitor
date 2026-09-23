import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from adapters import bonhams, sothebys
from adapters.market_common import page_data
from adapters.item_filter import exclusion_reason
from build import score
import comps

FIXTURES = Path(__file__).parent/'fixtures'

def html(p):
    return '<script id="__NEXT_DATA__" type="application/json">'+json.dumps({'props':{'pageProps':p}})+'</script>'

class MarketPilotTests(unittest.TestCase):
    def setUp(self):
        self.b = json.loads((FIXTURES/'bonhams.json').read_text())
        self.s = json.loads((FIXTURES/'sothebys.json').read_text())

    def test_bonhams_hammer_not_all_in(self):
        r=self.b['records'][0];lot=bonhams.parse_record(r,self.b['auction'])
        self.assertIsNotNone(lot)
        self.assertEqual(lot.sold_price,r['price']['hammerPrice'])
        self.assertNotEqual(lot.sold_price,r['price']['hammerPremium'])
        self.assertEqual(lot.sold_price_basis,'hammer')
        self.assertIsNone(lot.buyers_premium_pct)
        self.assertEqual(lot.ends_at,'')

    def test_unsold_and_withdrawn_not_marked_sold(self):
        for state in ('UNSOLD','WITHDRAWN','UNKNOWN'):
            r=copy.deepcopy(self.b['records'][0]);r['status']=state
            self.assertIsNone(bonhams.parse_record(r,self.b['auction']))

    def test_bonhams_pagination_and_repeat_guard(self):
        first={'auction':self.b['auction'],'lotData':{'auctionLots':[self.b['records'][0]],'nbHits':2}}
        second=copy.deepcopy(first);second['lotData']['auctionLots']=[self.b['records'][1]]
        with patch('adapters.bonhams.fetch',side_effect=[html(first),html(second)]) as get, patch('adapters.bonhams.time.sleep'):
            lots,report=bonhams.fetch_sale('https://www.bonhams.com/auction/31990/weekly-watches/')
            self.assertTrue(report['complete']);self.assertEqual(len(lots),2)
            self.assertTrue(get.call_args.args[0].endswith('?page=2'))
        with patch('adapters.bonhams.fetch',return_value=html(first)), patch('adapters.bonhams.time.sleep'):
            with self.assertRaisesRegex(ValueError,'repeated page'):bonhams.fetch_sale('https://www.bonhams.com/example/')

    def test_sothebys_exact_currency_estimate_and_partial_scope(self):
        lots, report=sothebys.parse_sale(html(self.s));lot=lots[0]
        self.assertEqual(lot.brand,'Patek Philippe')
        self.assertEqual((lot.estimate_low,lot.estimate_high,lot.estimate_currency),(30000,40000,'EUR'))
        self.assertEqual(lot.ends_at,'2026-10-07T12:01:00+00:00')
        self.assertIsNone(lot.current_bid) # starting bid is not a current bid
        self.assertFalse(report['complete']);self.assertEqual(report['expected_records'],107)

    def test_closed_sothebys_not_invented_result(self):
        for v in self.s['apolloCache'].values():
            if v.get('__typename')=='BidState':v['isClosed']=True
        self.assertEqual(sothebys.parse_sale(html(self.s))[0],[])

    def test_pilot_cannot_generate_arbitrage_or_comps(self):
        lot=bonhams.parse_record(self.b['records'][0],self.b['auction']).dict()
        self.assertEqual(comps.build_index([dict(lot,sold_usd=10000)]),{})
        lot.update(status='upcoming',fair_value_usd=50000,estimate_low=1000)
        score(lot,{'GBP':1.2},7.8)
        self.assertFalse(lot['arb_flag']);self.assertIsNone(lot['arb_margin_pct'])

    def test_block_page_fails_explicitly(self):
        with self.assertRaises(ValueError):page_data('<html>Access denied</html>')

    def test_french_complete_watch_preserved(self):
        self.assertIsNone(exclusion_reason('Patek Philippe Référence 5960 montre bracelet en acier'))
