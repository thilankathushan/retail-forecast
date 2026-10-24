import csv
from datetime import date, datetime
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from openpyxl import Workbook
from retail_forecast.pipeline import build_weekly, save_prepared
from retail_forecast.source import COLUMNS, SHEETS, import_workbook, sha256


class DataTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / 'input.csv'

    def write_rows(self, rows):
        with self.path.open('w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(COLUMNS)
            writer.writerows(rows)

    def row(self, **changes):
        record = dict(zip(COLUMNS, ['1', '10001', 'Synthetic item', 2, '2024-01-01 12:00:00', 1, '', 'UK']))
        record.update(changes)
        return list(record.values())

    def build(self, **kwargs):
        return build_weekly(self.path, date(2024, 1, 1), date(2024, 2, 4), **kwargs)

    def test_duplicate_retention_missing_customers_and_returns(self):
        row = self.row()
        self.write_rows([row, row, self.row(Invoice='C2', Quantity=-3),
                         self.row(Invoice='3', Quantity=-1, Price=0),
                         self.row(Invoice='C4', Quantity=5)])
        rows, report = self.build(assume_complete=True, audit_path=self.root / 'audit.csv')
        self.assertEqual(rows[0]['observed_units'], 4)
        self.assertEqual(report['recorded_return_units'], 4)
        self.assertEqual(report['counts']['cancellation_nonnegative'], 1)
        self.assertEqual(report['overlapping_flags']['accepted_missing_customer'], 2)
        self.assertEqual(report['overlapping_flags']['accepted_duplicate_retained'], 1)
        self.assertEqual({r['kind'] for r in report['returns_weekly']},
                         {'cancellation', 'negative_without_cancellation'})
        save_prepared(rows, report, self.root / 'out')
        self.assertTrue((self.root / 'out/returns_weekly.csv').exists())
        with (self.root / 'audit.csv').open() as stream:
            audit = list(csv.DictReader(stream))
        self.assertEqual(audit[1]['duplicate_of_row'], '2')

    def test_unknown_coverage_and_history_at_issue(self):
        self.write_rows([self.row()])
        unknown, _ = self.build()
        self.assertTrue(all(r['observed_units'] is None for r in unknown))
        self.assertEqual(unknown[0]['recorded_positive_units'], 2)
        observed, _ = self.build(assume_complete=True, min_history_weeks=4)
        self.assertEqual([r['history_eligible_at_issue'] for r in observed], [False]*4+[True])
        missing, _ = self.build(assume_complete=True, missing_days=[date(2024, 1, 15)])
        self.assertFalse(missing[-1]['history_eligible_at_issue'])
        self.assertIsNone(missing[2]['observed_units'])

    def test_explicit_rules(self):
        bad = [({'InvoiceDate': ''}, 'invalid_timestamp'),
               ({'InvoiceDate': '2024-01-01T12:00:00+00:00'}, 'invalid_timestamp'),
               ({'StockCode': ''}, 'missing_product'), ({'StockCode': '???'}, 'unrecognized_product_code'),
               ({'StockCode': 'POST'}, 'non_product_code'),
               ({'StockCode': 'gift_0001_10'}, 'non_product_code'),
               ({'Quantity': '1.5'}, 'invalid_quantity'), ({'Quantity': 'NaN'}, 'invalid_quantity'),
               ({'Price': 'inf'}, 'invalid_price'), ({'Price': '-1'}, 'nonpositive_price'),
               ({'Quantity': 0}, 'zero_quantity')]
        for changes, reason in bad:
            with self.subTest(reason=reason, changes=changes):
                self.write_rows([self.row(**changes)])
                _, report = self.build()
                self.assertEqual(report['counts'][reason], 1)
        self.write_rows([self.row(StockCode=c) for c in ['DCGS0058', 'PADS', 'SP1002', '47503j ']])
        _, report = self.build()
        self.assertEqual(report['counts']['accepted_rows'], 4)

    def test_workbook_both_sheets_and_schema(self):
        path = self.root / 'online_retail_II.xlsx'
        book = Workbook()
        book.remove(book.active)
        for name in SHEETS:
            sheet = book.create_sheet(name)
            sheet.append(COLUMNS)
            sheet.append(self.row(InvoiceDate=datetime(2024, 1, 1, 12)))
        book.save(path)
        book.close()
        archive = self.root / 'online_retail_ii.zip'
        with zipfile.ZipFile(archive, 'w') as z:
            z.write(path, path.name)
        (self.root / 'source.json').write_text(json.dumps({'archive_sha256': sha256(archive)}))
        manifest = import_workbook(self.root)
        self.assertEqual(manifest['sheet_rows'], dict.fromkeys(SHEETS, 1))
        self.assertEqual(manifest['input_rows'], 2)
        with (self.root / 'transactions.csv').open() as stream:
            self.assertEqual(len(list(csv.DictReader(stream))), 2)
        archive.write_bytes(b'corrupt')
        with self.assertRaises(ValueError):
            import_workbook(self.root)


if __name__ == '__main__':
    unittest.main()
