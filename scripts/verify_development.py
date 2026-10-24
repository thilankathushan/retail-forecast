"""Check saved development artifacts without reading holdout targets."""
import json
from pathlib import Path
import pandas as pd
from retail_forecast.evaluation import MODELS, metrics

root = Path('artifacts/uci/development')
report = json.loads((root / 'metrics.json').read_text())
pred = pd.read_csv(root / 'predictions.csv', dtype={'product_id': str})
audit = pd.read_csv(root / 'eligibility.csv', dtype={'product_id': str})
folds = pd.read_csv(root / 'folds.csv')
products = pd.read_csv(root / 'per_product.csv', dtype={'product_id': str})
assert not report['holdout_evaluated']
assert pred.issue_week.lt(report['protocol']['holdout_start']).all()
assert set(pred.model) == set(MODELS)
keys = None
for model, group in pred[pred.scored].groupby('model'):
    current = set(zip(group.issue_week, group.product_id))
    assert len(current) == len(group)
    assert keys is None or current == keys
    keys = current
    for key, value in metrics(group.actual, group.prediction).items():
        assert report['models'][model][key] == value
    rows = products[products.model.eq(model)]
    assert rows.rows.sum() == len(group)
    assert rows.absolute_error.sum() == report['models'][model]['absolute_error']
    assert rows.actual_units.sum() == report['models'][model]['actual_units']
assert len(keys) == int(audit.scored.sum())
assert set(pred.issue_week) == set(folds.loc[folds.split.eq('development'), 'issue_week'])
assert not folds.loc[folds.split.eq('holdout'), 'executed'].any()
assert (folds.train_end_exclusive == folds.issue_week).all()
print('Common cohorts, saved metrics, product totals, folds and unused holdout verified.')
