import copy
import json
import tempfile
import unittest
from pathlib import Path
from contextlib import ExitStack
from unittest.mock import patch
from adapters.base import Lot
from adapters import sothebys
from lifecycle import active, normalize, preserve_missing, merge_archive
import build

class LifecycleTests(unittest.TestCase):
    def old(self, **kwargs):
        lot=dict(lot_id='bezel_1', platform='Bezel', title_raw='Cartier Tank', status='live',
                 last_seen='2026-09-23T00:00:00Z', first_seen='2026-08-01T00:00:00Z',
                 arb_flag=True, arb_margin_pct=50, current_bid_usd=1200, is_new=True)
        lot.update(kwargs);return lot

    def test_failed_source_preserved_without_refresh_or_alert(self):
        old=self.old();health=[{'source':'bezel','state':'failed'}]
        rows=preserve_missing([],{'bezel_1':old},health,'2026-09-25T00:00:00Z')
        l=rows[0];self.assertTrue(l['data_stale']);self.assertFalse(active(l))
        self.assertEqual(l['last_seen'],old['last_seen']);self.assertEqual(l['current_bid_usd'],1200)
        self.assertFalse(l['arb_flag']);self.assertIsNone(l['arb_margin_pct']);self.assertFalse(l['is_new'])
        self.assertEqual(health[0]['retained_stale'],1);self.assertNotIn('data_stale',old)

    def test_missing_on_success_is_not_a_sale(self):
        rows=preserve_missing([],{'bezel_1':self.old()},[{'source':'bezel','state':'returned'}],'now')
        self.assertEqual(rows[0]['stale_reason'],'not_observed');self.assertEqual(rows[0]['status'],'live')
        again=preserve_missing([],{'bezel_1':rows[0]},[],'later')
        self.assertEqual(again[0]['missing_since'],'now')

    def test_fresh_observation_replaces_stale(self):
        current=[self.old(data_stale=False, status='unsold')]
        rows=preserve_missing(current,{'bezel_1':self.old(data_stale=True)},[],'now')
        self.assertEqual(len(rows),1);self.assertFalse(rows[0]['data_stale']);self.assertEqual(rows[0]['status'],'unsold')

    def test_peripherals_never_resurrected(self):
        self.assertEqual(preserve_missing([],{'bezel_1':self.old(title_raw='Cartier backpack')},[],'now'),[])

    def test_unknown_results_not_sold_or_scored(self):
        self.assertEqual(normalize(self.old(status='past'))['status'],'ended')
        self.assertEqual(normalize(self.old(status='past',sale_result='sold'))['status'],'past')
        for status in ('unknown','ended','unsold','withdrawn'):
            l=normalize(self.old(status=status,sold_price=1000,sold_usd=1000))
            self.assertIsNone(l['sold_price']);self.assertFalse(l['arb_flag'])
            l.update(fair_value_usd=10000,estimate_currency='USD',current_bid=1000)
            build.score(l,{'USD':1},7.8);self.assertIsNone(l['arb_margin_pct'])

    def test_archive_corrected_or_updated(self):
        old=self.old(status='past',sold_usd=1000)
        self.assertEqual(merge_archive([old],[self.old(status='unsold')]),[])
        updated=merge_archive([old],[self.old(status='past',sold_usd=2000)])
        self.assertEqual(updated[0]['sold_usd'],2000)
        self.assertEqual(merge_archive([old],[self.old(status='unsold',data_stale=True)]),[old])

    def test_full_build_failure_retains_and_recovery_replaces(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            for key,file in [('OUT_PATH','lots.json'),('ARCHIVE_PATH','archive.json'),('META_PATH','meta.json')]:
                stack.enter_context(patch.object(build,key,str(Path(tmp)/file)))
            old=self.old(brand='Cartier',estimate_currency='USD',current_bid=1000)
            Path(build.OUT_PATH).write_text(json.dumps([old]))
            modules={}
            for name in ('phillips','loupethis','bezel','antiquorum','watchcollecting','monacolegend','allu','crott'):
                modules[name]=stack.enter_context(patch(f'build.{name}.run',return_value=[]))
            stack.enter_context(patch.dict('os.environ',{'EXPERIMENTAL_MARKETS':'0'}))
            stack.enter_context(patch('build.get_fx',return_value=({'USD':1},7.8)))
            c24=stack.enter_context(patch('build.c24.enrich'))
            notify=stack.enter_context(patch('build.notify'))
            modules['phillips'].return_value=[Lot(lot_id='phillips_2',platform='Phillips',platform_type='major_house',source_url='https://example.com',brand='Cartier',title_raw='Cartier Tank')]
            modules['bezel'].side_effect=RuntimeError('offline')
            build.main()
            rows=json.loads(Path(build.OUT_PATH).read_text());retained=next(l for l in rows if l['lot_id']=='bezel_1')
            self.assertTrue(retained['data_stale']);self.assertEqual(retained['last_seen'],old['last_seen'])
            self.assertFalse(any(l['lot_id']=='bezel_1' for l in notify.call_args.args[0]))
            modules['bezel'].side_effect=None
            modules['bezel'].return_value=[Lot(lot_id='bezel_1',platform='Bezel',platform_type='online',source_url='https://example.com',brand='Cartier',title_raw='Cartier Tank',status='live')]
            build.main()
            rows=json.loads(Path(build.OUT_PATH).read_text());fresh=next(l for l in rows if l['lot_id']=='bezel_1')
            self.assertFalse(fresh['data_stale']);self.assertEqual(fresh['first_seen'],old['first_seen'])
            self.assertNotEqual(fresh['last_seen'],old['last_seen']);self.assertFalse(fresh['is_new'])

class SothebysStateTests(unittest.TestCase):
    def setUp(self):
        p=json.loads((Path(__file__).parent/'fixtures/sothebys.json').read_text())
        self.cache=p['apolloCache'];self.a=next(v for v in self.cache.values() if v.get('__typename')=='Auction')
        self.r=next(v for v in self.cache.values() if v.get('__typename')=='LotCard')
        self.bid=self.cache[self.r['bidState']['__ref']]

    def parse(self):return sothebys.parse_cards([self.r],self.a,self.cache)[0]

    def test_accepting_bids_has_real_bid_not_starting_bid(self):
        self.bid['bidTypeV2']['timedBidPhase']='AcceptingBids'
        self.bid['currentBidV2']={'currency':'EUR','amount':'31000'}
        self.assertEqual(self.parse().status,'live');self.assertEqual(self.parse().current_bid,31000)
        self.bid['currentBidV2']=None;self.assertIsNone(self.parse().current_bid)

    def test_currency_mismatch_not_used(self):
        self.bid['bidTypeV2']['timedBidPhase']='AcceptingBids'
        self.bid['currentBidV2']={'currency':'USD','amount':'31000'}
        self.assertIsNone(self.parse().current_bid)

    def test_closed_hidden_outcome_and_sold(self):
        self.bid['isClosed']=True;self.bid['sold']={'__typename':'ResultHidden'}
        self.assertEqual(self.parse().status,'ended');self.assertIsNone(self.parse().sold_price)
        self.bid['sold']={'__typename':'ResultVisible','isSold':True,'premiums':{'finalPriceV2':{'currency':'EUR','amount':'40000'}}}
        self.assertEqual(self.parse().status,'past');self.assertEqual(self.parse().sold_price_basis,'all_in')
        self.assertEqual(self.parse().sold_price,40000)

    def test_unknown_phase_and_withdrawal_retained(self):
        self.bid['bidTypeV2']['timedBidPhase']='NewFuturePhase'
        self.assertEqual(self.parse().status,'unknown')
        self.r['withdrawnState']['state']='Withdrawn'
        self.assertEqual(self.parse().status,'withdrawn');self.assertIsNone(self.parse().sold_price)

    def test_reinstated_lot_accepting_bids(self):
        self.r['withdrawnState']['state']='UnWithdrawn'
        self.bid['bidTypeV2']['timedBidPhase']='AcceptingBids'
        self.assertEqual(self.parse().status,'live')
