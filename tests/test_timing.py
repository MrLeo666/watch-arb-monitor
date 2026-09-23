import unittest
from unittest.mock import patch, Mock
from adapters.base import normalize_end
from adapters import loupethis


class TimingTests(unittest.TestCase):
    def test_exact_timestamp_normalized(self):
        self.assertEqual(normalize_end('2026-09-23T20:30:00+08:00'), '2026-09-23T12:30:00+00:00')

    def test_ambiguous_times_rejected(self):
        for value in ('2026-09-23', '', None, 'invalid', '2026-09-23T12:30:00'):
            self.assertEqual(normalize_end(value), '')

    def test_explicit_utc_field(self):
        self.assertEqual(normalize_end('2026-09-23T12:30:00', assume_utc=True), '2026-09-23T12:30:00+00:00')

    @patch('adapters.loupethis.requests.get')
    def test_adapter_keeps_full_end_time(self, get):
        get.return_value = Mock(json=lambda: {'data': [{'id': 1, 'attributes': {
            'title': 'Cartier Tank', 'ends_at': '2026-09-23T12:30:00Z'}}]})
        lot = loupethis.run()[0]
        self.assertEqual(lot.ends_at, '2026-09-23T12:30:00+00:00')
        self.assertEqual(lot.auction_date, '2026-09-23')
