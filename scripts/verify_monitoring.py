"""Verify saved simulated monitoring ledgers against exports and frozen results."""
import json
from pathlib import Path
import sqlite3
from contextlib import closing
import math
import pandas as pd
from retail_forecast.monitoring import week_close

root = Path(__file__).resolve().parents[1]
folders = list((root / 'artifacts/uci/monitoring').glob('*/*/summary.json'))
assert len(folders) == 8
for path in folders:
    folder = path.parent
    summary = json.loads(path.read_text())
    forecasts = pd.read_csv(folder / 'forecasts.csv')
    scores = pd.read_csv(folder / 'scores.csv')
    assert summary['simulation'] is True
    assert not forecasts.duplicated(['target_week', 'product_id']).any()
    with closing(sqlite3.connect(folder / 'ledger.sqlite')) as db:
        count = db.execute("SELECT COUNT(*) FROM entries WHERE kind='forecast'").fetchone()[0]
    assert count == len(forecasts) == summary['forecasts']
    assert scores.rows.sum() == summary['scored_rows']
    for score in scores.itertuples():
        assert pd.Timestamp(score.scored_at) >= week_close(score.target_week)
        assert pd.Timestamp(score.scored_at) >= pd.Timestamp(score.actual_available_at)
    if summary['kind'] == 'real':
        assert count == 59395 and len(scores) == 13
        assert math.isclose(scores.absolute_error.sum()/scores.rows.sum(), 18.9451745693, abs_tol=1e-9)
        assert math.isclose(scores.absolute_error.sum()/scores.actual_units.sum(), .5971142372, abs_tol=1e-9)
        assert math.isclose((scores.coverage_95*scores.rows).sum()/scores.rows.sum(), .9417964475, abs_tol=1e-9)
print('Verified eight replay ledgers, unique forecasts, delayed scoring, and frozen real metrics.')
