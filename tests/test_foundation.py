from datetime import date
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import pandas as pd

from retail_forecast.baseline import backtest, read_weekly, train, forecast
from retail_forecast.config import load_config

FIXTURE = Path(__file__).parent / 'fixtures/synthetic_transactions.csv'


class FoundationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.config = self.root / 'config.toml'
        self.config.write_text('random_seed = 17\n')

    def test_config_paths_and_validation(self):
        config = load_config(self.config)
        self.assertEqual(config.data_dir, self.root / 'data/processed')
        self.assertEqual(config.random_seed, 17)
        for text in ['horizon_weeks = 2', 'random_seed = true', 'random_seed = -1',
                     'data_dir = ""', 'typo = 1', 'timezone = "UTC"']:
            with self.subTest(text=text):
                self.config.write_text(text)
                with self.assertRaises(ValueError):
                    load_config(self.config)

    def test_chronology_and_zero_denominator(self):
        frame = pd.DataFrame({'product_id': ['A'] * 4,
                              'week_start': pd.to_datetime(['2024-01-01', '2024-01-08', '2024-01-22', '2024-01-29']),
                              'observed_units': [2, 5, 7, 0], 'status': ['observed'] * 4})
        pairs, report = backtest(frame)
        self.assertEqual(pairs.prediction.tolist(), [2, 7])
        self.assertEqual(report['mae'], 5)
        self.assertEqual(report['wape'], 2)
        frame.observed_units = 0
        self.assertIsNone(backtest(frame)[1]['wape'])
        state = train(frame, date(2024, 1, 8), load_config(self.config), FIXTURE)
        self.assertEqual(state['predictions'], {'A': 0})
        frame.loc[frame.week_start.gt('2024-01-01'), 'observed_units'] = 999
        self.assertEqual(train(frame, date(2024, 1, 8), load_config(self.config), FIXTURE), state)

    def test_weekly_contract(self):
        path = self.root / 'weekly.csv'
        header = 'product_id,week_start,observed_units,status\n'
        for row in ['A,2024-01-02,1,observed\n', 'A,2024-01-01,,observed\n',
                    'A,2024-01-01,0,missing_observation\n', 'A,2024-01-01,-1,observed\n',
                    'A,2024-01-01,inf,observed\n', 'A,2024-01-01,1,unknown\n']:
            path.write_text(header + row)
            with self.subTest(row=row), self.assertRaises(ValueError):
                read_weekly(path)
        path.write_text(header + '001,2024-01-01,0,observed\n')
        self.assertEqual(read_weekly(path).iloc[0].product_id, '001')
        with self.assertRaises(ValueError):
            backtest(read_weekly(path))

    def run_cli(self, *args):
        return subprocess.run([sys.executable, '-m', 'retail_forecast', '--config', str(self.config), *args],
                              cwd=self.root, capture_output=True, text=True)

    def test_cli_end_to_end_from_other_directory(self):
        result = self.run_cli('prepare', '--input', str(FIXTURE.resolve()), '--coverage-start',
                              '2024-01-03', '--coverage-end', '2024-01-30', '--assume-complete')
        self.assertEqual(result.returncode, 0, result.stderr)
        for args in [('backtest-smoke',), ('train', '--issue-week', '2024-01-29'),
                     ('forecast', '--issue-week', '2024-01-29')]:
            result = self.run_cli(*args)
            self.assertEqual(result.returncode, 0, result.stderr)
        rows = pd.read_csv(self.root / 'artifacts/forecast.csv')
        self.assertEqual(rows.prediction.tolist(), [3, 0])
        report = json.loads((self.root / 'artifacts/backtest.json').read_text())
        self.assertEqual(report['rows'], 3)
        result = self.run_cli('forecast', '--issue-week', '2024-02-05')
        self.assertEqual(result.returncode, 2)
        self.assertIn('run train', result.stderr)
        self.assertNotIn('Traceback', result.stderr)

    def test_errors_and_corrupt_artifact(self):
        result = self.run_cli('backtest-smoke')
        self.assertEqual(result.returncode, 2)
        self.assertIn('Check --config', result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        model = self.root / 'bad.json'
        for contents in ['[]', '{}', '{']:
            model.write_text(contents)
            with self.assertRaises(ValueError):
                forecast(model, '2024-01-29', load_config(self.config))


if __name__ == '__main__':
    unittest.main()
