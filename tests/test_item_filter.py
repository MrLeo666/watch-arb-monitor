import unittest
from adapters.item_filter import exclusion_reason
import comps


class ItemFilterTests(unittest.TestCase):
    def test_standalone_accessories_excluded(self):
        for title in (
            'PATEK PHILIPPE, VINTAGE WRISTWATCH BOX, CANVAS',
            'PATEK PHILIPPE, SET OF TWO ACCESSORIES FOR REF. 5004',
            'F.P. JOURNE, PRESENTATION BOX, WOOD',
            'F.P. JOURNE, HOROLOGICAL BOOK',
            'PATEK PHILIPPE, CALATRAVA-STYLE DEPLOYANT CLASP',
            'PATEK PHILIPPE, SILVER DIAL WITH YELLOW GOLD INDEXES',
            'Patek Philippe leather strap',
            'Cartier certificate',
            'PATEK PHILIPPE, VIDE-POCHE COLLECTION 2010',
            '2023 F.P. Journe Souverain Table Clock Ref. N/A',
        ):
            with self.subTest(title=title):
                self.assertIsNotNone(exclusion_reason(title))

    def test_complete_watches_preserved(self):
        for title in (
            'Patek Philippe Perpetual Calendar 3940J Second Series 18K YG Box and Papers',
            'Cartier Tank Solo Small Steel / Silvered / Roman / Bracelet',
            'Cartier Santos Dumont Large Steel with black lacquer / Skeletonized / Strap',
            'Patek Philippe Aquanaut / Black / Bracelet',
            'Cartier wristwatch with presentation box',
            'Cartier wristwatch, presentation box and certificate',
            'Cartier Tank with box and papers',
            'A.LANGE & SÖHNE, HUNTING CASE POCKET WATCH, 18K YELLOW GOLD',
            '2014 MB&F SIDEWINDER - HOROLOGICAL MACHINE No.3',
        ):
            with self.subTest(title=title):
                self.assertIsNone(exclusion_reason(title))

    def test_archive_accessories_not_used_as_comparables(self):
        idx = comps.build_index([
            {'status':'past', 'brand':'Cartier', 'sold_usd':1000, 'title_raw':'Cartier presentation box'},
            {'status':'past', 'brand':'Cartier', 'sold_usd':5000, 'title_raw':'Cartier Tank with box'},
        ])
        self.assertEqual(len(idx['Cartier']), 1)
        self.assertEqual(idx['Cartier'][0][1], 5000)
