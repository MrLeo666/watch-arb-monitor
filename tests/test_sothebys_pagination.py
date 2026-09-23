import copy
import json
import unittest
from unittest.mock import patch, Mock
from adapters import sothebys

URL = 'https://www.sothebys.com/en/buy/auction/2026/test'
HTML = '<script id="__NEXT_DATA__">'+json.dumps({'props':{'pageProps':{'auctionId':'test-id'}}})+'</script>'


def page(ids, more, total=5):
    return {'auctionId':'test-id','departmentNames':['Watches'],
            'lotCardsConnection':{'lots':[{'lotId':i} for i in ids], 'totalCount':total, 'hasNextPage':more}}

class PaginationTests(unittest.TestCase):
    def run_pages(self, pages, **kwargs):
        with patch('adapters.sothebys.fetch',return_value=HTML), patch('adapters.sothebys.request_page',side_effect=pages) as request, patch('adapters.sothebys.parse_cards',return_value=[]) as parse, patch('adapters.sothebys.time.sleep'):
            result = sothebys.fetch_sale(URL,**kwargs)
            return result,request.call_args_list,parse.call_args.args[0]

    def test_all_pages_and_offsets(self):
        (_,report),calls,cards=self.run_pages([page(['a','b'],True),page(['c','d'],True),page(['e'],False)])
        self.assertEqual([c.args[1] for c in calls],[0,2,4])
        self.assertEqual(len(cards),5);self.assertTrue(report['complete'])
        self.assertEqual(report['catalogue_records'],5)
        self.assertEqual([p['new_unique'] for p in report['pages']],[2,2,1])

    def test_overlap_deduplicated(self):
        (_,report),_,cards=self.run_pages([page(['a','b'],True,3),page(['b','c'],False,3)])
        self.assertEqual(len(cards),3);self.assertTrue(report['complete'])

    def test_repeated_page_fails(self):
        with self.assertRaisesRegex(ValueError,'no progress'):
            self.run_pages([page(['a','b'],True),page(['a','b'],True)])

    def test_incomplete_terminal_page_fails(self):
        with self.assertRaisesRegex(ValueError,'Incomplete'):
            self.run_pages([page(['a','b'],False)])

    def test_changing_total_fails(self):
        with self.assertRaisesRegex(ValueError,'total changed'):
            self.run_pages([page(['a','b'],True),page(['c'],False,3)])

    def test_empty_catalogue_is_complete_but_empty(self):
        (_,report),_,_=self.run_pages([page([],False,0)])
        self.assertEqual(report['catalogue_records'],0)

    def test_page_limit_fails(self):
        with self.assertRaisesRegex(ValueError,'safety limit'):
            self.run_pages([page(['a'],True)],max_pages=1)

    def test_graphql_errors_fail_even_with_data(self):
        response=Mock();response.json.return_value={'errors':[{'message':'error'}],'data':{'auction':page([],False,0)}}
        with patch('adapters.sothebys.requests.post',return_value=response):
            with self.assertRaisesRegex(ValueError,'query returned errors'):
                sothebys.request_page('test-id',0,48)

    def test_wrong_auction_rejected(self):
        response=Mock();response.json.return_value={'data':{'auction':page([],False,0)}}
        with patch('adapters.sothebys.requests.post',return_value=response):
            with self.assertRaisesRegex(ValueError,'mismatched'):
                sothebys.request_page('other-id',0,48)
