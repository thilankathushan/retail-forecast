import json
from pathlib import Path
import tempfile
import unittest
import pandas as pd

from retail_forecast.evaluation import evaluate_development, folds, load_protocol, metrics, summarize
from retail_forecast.baseline import read_weekly


def protocol():
    return dict(train_start='2024-01-01', development_start='2024-01-29', holdout_start='2024-02-12',
                holdout_end_exclusive='2024-02-26', min_history_weeks=2, trailing_weeks=2,
                seasonal_weeks=4, horizon_weeks=1, timezone='Europe/London', seasonal_fallback='trailing_average')


def panel():
    records = []
    for product, weeks, values in [('A', 0, [1, 2, 3, 4, 10, 20, 999]),
                                  ('ZERO', 0, [0]*7), ('NEW', 4, [5, 6, 7]),
                                  ('SHORT', 3, [8, 9, 10, 11]), ('GAP', 0, [1, 2, None, 4, 5, 6, 7])]:
        for i, value in enumerate(values):
            records.append(dict(product_id=product, week_start=pd.Timestamp('2024-01-01') + pd.Timedelta(weeks=i+weeks),
                                observed_units=value, status='observed' if value is not None else 'missing_observation'))
    return pd.DataFrame(records)


class EvaluationTests(unittest.TestCase):
    def test_known_predictions_and_common_cohort(self):
        predictions, audit, _ = evaluate_development(panel(), protocol())
        first = predictions[(predictions.product_id == 'A') & (predictions.issue_week == '2024-01-29')]
        self.assertEqual(dict(zip(first.model, first.prediction)),
                         {'last_observed_week': 4, 'trailing_average': 3.5, 'seasonal_naive': 1})
        second = predictions[(predictions.product_id == 'A') & (predictions.issue_week == '2024-02-05')]
        self.assertEqual(dict(zip(second.model, second.prediction)),
                         {'last_observed_week': 10, 'trailing_average': 7, 'seasonal_naive': 2})
        gap = predictions[(predictions.product_id == 'GAP') & (predictions.model == 'seasonal_naive')]
        self.assertEqual(gap.prediction.tolist(), [4.5])
        self.assertTrue(gap.seasonal_fallback.all())
        self.assertEqual(predictions.groupby(['issue_week', 'product_id']).size().unique().tolist(), [3])
        statuses = audit[audit.issue_week.eq('2024-01-29')].set_index('product_id').history_status.to_dict()
        self.assertEqual(statuses['NEW'], 'new_product')
        self.assertEqual(statuses['SHORT'], 'short_history')
        self.assertEqual(statuses['GAP'], 'incomplete_recent_history')
        self.assertTrue(audit[audit.product_id.eq('ZERO')].scored.all())
        self.assertTrue(audit[audit.product_id.eq('ZERO')].all_zero_history.all())

    def test_boundaries_and_timestamps(self):
        definition = folds(protocol())
        self.assertEqual(definition.split.tolist(), ['development']*2 + ['holdout']*2)
        self.assertTrue((definition.issue_week == definition.train_end_exclusive).all())
        self.assertEqual(definition.iloc[0].issued_at, '2024-01-29T00:00:00+00:00')
        self.assertEqual(definition.iloc[0].target_end_exclusive, '2024-02-05')
        p = protocol() | dict(development_start='2024-04-01', holdout_start='2024-04-08', holdout_end_exclusive='2024-04-15')
        self.assertEqual(folds(p).iloc[0].issued_at, '2024-04-01T00:00:00+01:00')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'protocol.json'
            path.write_text(json.dumps(protocol() | {'development_start':'2024-01-30'}))
            with self.assertRaises(ValueError): load_protocol(path)

    def test_future_and_holdout_invariance(self):
        original = panel()
        before, audit, _ = evaluate_development(original, protocol())
        changed = original.copy()
        changed.loc[changed.week_start.ge('2024-02-12'), 'observed_units'] = 999999
        after, other, _ = evaluate_development(changed, protocol())
        pd.testing.assert_frame_equal(before, after)
        pd.testing.assert_frame_equal(audit, other)
        changed.loc[changed.week_start.ge('2024-01-29'), 'observed_units'] = 888
        after, _, _ = evaluate_development(changed, protocol())
        pd.testing.assert_series_equal(before[before.issue_week.eq('2024-01-29')].prediction,
                                       after[after.issue_week.eq('2024-01-29')].prediction)

    def test_metrics_and_missing_target(self):
        result = metrics([0, 10], [5, 5])
        self.assertEqual(result['mae'], 5)
        self.assertEqual(result['wape'], 1)
        self.assertEqual(metrics([0, 0], [1, 3])['mae'], 2)
        self.assertIsNone(metrics([0, 0], [1, 3])['wape'])
        self.assertIsNone(metrics([], [])['mae'])
        with self.assertRaises(ValueError): metrics([1], [])
        data = panel()
        data.loc[(data.product_id == 'A') & data.week_start.eq('2024-02-05'), 'observed_units'] = float('nan')
        predictions, audit, _ = evaluate_development(data, protocol())
        self.assertEqual(len(predictions[(predictions.product_id == 'A') & ~predictions.scored]), 3)
        report = summarize(predictions, audit)
        self.assertEqual(report['coverage']['eligible_missing_target'], 1)
        self.assertEqual(len({m['rows'] for m in report['models'].values()}), 1)

    def test_holdout_values_are_not_validated_or_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'weekly.csv'
            path.write_text('product_id,week_start,observed_units,status\nA,2024-01-01,1,observed\nA,2024-02-12,DO_NOT_USE,observed\n')
            result = read_weekly(path, before='2024-02-12')
            self.assertEqual(result.observed_units.tolist(), [1])
