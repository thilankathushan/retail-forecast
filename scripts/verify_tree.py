"""Reconcile tree results and trusted artifact replay; no holdout access."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from retail_forecast.tree import forecast_saved
from retail_forecast.evaluation import metrics

root = Path('artifacts/uci/tree')
report = json.loads((root/'metrics.json').read_text())
pred = pd.read_csv(root/'predictions.csv', dtype={'product_id':str})
base = pd.read_csv('artifacts/uci/development/predictions.csv', dtype={'product_id':str})
reference = base[base.model.eq('last_observed_week') & base.scored]
expected = set(zip(reference.issue_week, reference.product_id))
for name, group in pred[pred.scored].groupby('model'):
    assert len(group) == len(expected)
    assert set(zip(group.issue_week,group.product_id)) == expected
    for key,value in metrics(group.actual,group.prediction).items():
        assert np.isclose(value, report['candidates'][name][key])
assert pred.issue_week.lt('2011-09-05').all()
assert not report['holdout_evaluated']
origin = report['metadata']['training_end_exclusive']
replay = forecast_saved(Path('data/processed/uci/weekly.csv'),Path('models/uci/tree.joblib'),origin)
expected_pred = pred[pred.model.eq(report['selected']) & pred.issue_week.eq(origin)].sort_values('product_id')
np.testing.assert_allclose(replay.sort_values('product_id').prediction,expected_pred.prediction,rtol=1e-12)
try:
    forecast_saved(Path('data/processed/uci/weekly.csv'),Path('models/uci/tree.joblib'),'2011-09-05')
except ValueError as exc:
    assert 'holdout' in str(exc)
else:
    raise AssertionError('Holdout guard failed')
print('Tree cohorts, metrics, reload/replay parity and holdout guard passed.')
