from datetime import date
from pathlib import Path
import tempfile
import unittest
from retail_forecast.pipeline import build_weekly

FIXTURE = Path(__file__).parent / 'fixtures/synthetic_transactions.csv'


class PipelineTests(unittest.TestCase):
    def run_fixture(self, missing=()):
        return build_weekly(FIXTURE, date(2024, 1, 3), date(2024, 1, 30), missing, assume_complete=True)

    def test_cleaning_accounting(self):
        _, report = self.run_fixture()
        counts = report['counts']
        self.assertEqual(counts['input_rows'], 11)
        self.assertEqual(counts['accepted_rows'], 4)
        self.assertEqual(counts['return_or_adjustment'], 2)
        self.assertEqual(sum(v for k, v in counts.items() if k != 'input_rows'), 11)
        for reason in ['missing_product', 'invalid_timestamp', 'invalid_quantity', 'nonpositive_price', 'outside_coverage']:
            self.assertEqual(counts[reason], 1)

    def test_partial_zero_and_product_entry(self):
        rows, _ = self.run_fixture()
        a = [r for r in rows if r['product_id'] == '10001']
        self.assertEqual([r['observed_units'] for r in a], [None, 4, 0, 3, None])
        self.assertEqual(a[0]['status'], 'partial_week')
        self.assertEqual(a[-1]['status'], 'partial_week')
        self.assertEqual(min(r['week_start'] for r in rows if r['product_id'] == '10002'), '2024-01-15')

    def test_missing_week_is_not_zero_even_if_some_sales_exist(self):
        rows, _ = self.run_fixture([date(2024, 1, 16)])
        week = [r for r in rows if r['week_start'] == '2024-01-15']
        self.assertTrue(all(r['observed_units'] is None for r in week))
        self.assertTrue(all(r['status'] == 'missing_observation' for r in week))

    def test_invalid_contract(self):
        with self.assertRaises(ValueError):
            self.run_fixture([date(2025, 1, 1)])
        with self.assertRaises(ValueError):
            build_weekly(FIXTURE, date(2024, 2, 1), date(2024, 1, 1))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'bad.csv'
            path.write_text('StockCode,Quantity\nA,1\n')
            with self.assertRaises(ValueError):
                build_weekly(path, date(2024, 1, 1), date(2024, 1, 7))

    def test_future_product_does_not_change_past_panel(self):
        rows, _ = self.run_fixture()
        early, _ = build_weekly(FIXTURE, date(2024, 1, 3), date(2024, 1, 14), assume_complete=True)
        self.assertEqual([r for r in rows if r['week_start'] <= '2024-01-08'], early)

    def test_reproducible(self):
        self.assertEqual(self.run_fixture(), self.run_fixture())


if __name__ == '__main__':
    unittest.main()
