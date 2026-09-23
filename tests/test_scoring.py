import unittest
from contextlib import ExitStack
from unittest.mock import patch

import build


class ScoringTests(unittest.TestCase):
    def lot(self, **changes):
        lot = dict(estimate_currency="USD", current_bid=1000,
                   fair_value_usd=2000, status="live", buyers_premium_pct=0)
        lot.update(changes)
        return lot

    def test_zero_premium_is_preserved(self):
        lot = build.score(self.lot(), {"USD": 1}, 7.8)
        self.assertEqual(lot["arb_margin_pct"], 68.4)
        self.assertTrue(lot["arb_flag"])

    def test_missing_premium_uses_default(self):
        lot = build.score(self.lot(buyers_premium_pct=None), {"USD": 1}, 7.8)
        self.assertEqual(lot["arb_margin_pct"], 35.9)

    def test_c24_net_proceeds_are_not_discounted_twice(self):
        lot = build.score(self.lot(fair_value_usd=1700, fair_value_source="C24(4)"), {"USD": 1}, 7.8)
        self.assertEqual(lot["arb_margin_pct"], 62.7)

    def test_unknown_currency_clears_previous_score(self):
        for currency in ("XYZ", "", None):
            with self.subTest(currency=currency):
                lot = build.score(self.lot(), {"USD": 1}, 7.8)
                lot["estimate_currency"] = currency
                build.score(lot, {"USD": 1}, 7.8)
                self.assertIsNone(lot["current_bid_usd"])
                self.assertIsNone(lot["arb_margin_pct"])
                self.assertFalse(lot["arb_flag"])

    def test_native_currency_converted(self):
        lot = build.score(self.lot(estimate_currency=" eur ", estimate_low=800), {"EUR": 1.2}, 7.8)
        self.assertEqual(lot["current_bid_usd"], 1200)
        self.assertEqual(lot["estimate_low_usd"], 960)
        self.assertEqual(lot["estimate_low_hkd"], 7488)

    def test_rescore_clears_removed_prices(self):
        lot = build.score(self.lot(sold_price=1500), {"USD": 1}, 7.8)
        lot.update(current_bid=None, sold_price=None, fair_value_usd=None)
        build.score(lot, {"USD": 1}, 7.8)
        self.assertIsNone(lot["sold_usd"])
        self.assertIsNone(lot["current_bid_usd"])
        self.assertIsNone(lot["arb_margin_pct"])
        self.assertFalse(lot["arb_flag"])

    def test_past_lots_are_not_opportunities(self):
        lot = build.score(self.lot(status="past", sold_price=1500), {"USD": 1}, 7.8)
        self.assertFalse(lot["arb_flag"])
        self.assertIsNone(lot["arb_margin_pct"])
        self.assertEqual(lot["sold_usd"], 1500)

    def test_zero_bid_does_not_use_estimate(self):
        lot = build.score(self.lot(current_bid=0, estimate_low=1000), {"USD": 1}, 7.8)
        self.assertIsNone(lot["arb_margin_pct"])

    def test_empty_scrape_does_not_write_files_or_notify(self):
        with ExitStack() as stack:
            stack.enter_context(patch("build.load_previous", return_value={}))
            stack.enter_context(patch("build.get_fx", return_value=({"USD": 1}, 7.8)))
            for name in ("phillips", "loupethis", "bezel", "antiquorum",
                         "watchcollecting", "monacolegend", "allu", "crott"):
                stack.enter_context(patch(f"build.{name}.run", return_value=[]))
            file_open = stack.enter_context(patch("builtins.open"))
            notify = stack.enter_context(patch("build.notify"))
            with self.assertRaisesRegex(RuntimeError, "preserving existing data"):
                build.main()
            file_open.assert_not_called()
            notify.assert_not_called()

    @patch.dict("os.environ", {"TG_TOKEN": "test", "TG_CHAT": "test"})
    @patch("build.requests.post")
    def test_notification_uses_native_currency(self, post):
        build.notify([self.lot(estimate_currency="EUR", brand="Cartier",
                              platform="Example", title_raw="Watch", source_url="https://example.com")])
        self.assertIn("現時出價 EUR 1,000", post.call_args.kwargs["data"]["text"])


if __name__ == "__main__":
    unittest.main()
