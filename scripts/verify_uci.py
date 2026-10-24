"""Reconcile the prepared UCI run; execute from the project directory."""
from collections import Counter
import csv
import json
from pathlib import Path

import pandas as pd

from retail_forecast.source import sha256

source = json.loads(Path('data/raw/source.json').read_text())
quality = json.loads(Path('data/processed/uci/quality.json').read_text())
weekly = pd.read_csv('data/processed/uci/weekly.csv', dtype={'product_id': str})
returns = pd.read_csv('data/processed/uci/returns_weekly.csv', dtype={'product_id': str})
assert source['input_rows'] == sum(source['sheet_rows'].values()) == 1067371
assert quality['counts']['input_rows'] == source['input_rows']
assert sum(v for k, v in quality['counts'].items() if k != 'input_rows') == source['input_rows']
assert quality['source_sha256'] == source['normalized_csv_sha256'] == sha256('data/raw/transactions.csv')
assert weekly.recorded_positive_units.sum() == quality['accepted_positive_units']
assert returns.recorded_return_units.sum() == quality['recorded_return_units']
assert len(weekly) == quality['weekly_rows']
assert weekly.product_id.nunique() == quality['products']
assert not weekly.duplicated(['product_id', 'week_start']).any()
assert weekly.loc[weekly.status.ne('observed'), 'observed_units'].isna().all()
assert weekly.loc[weekly.status.eq('observed'), 'observed_units'].notna().all()
assert weekly.history_eligible_at_issue.eq(
    weekly.prior_consecutive_observed_weeks.ge(quality['min_history_weeks'])).all()
with Path('data/processed/uci/row_audit.csv').open() as stream:
    audited = Counter(row['outcome'] for row in csv.DictReader(stream))
assert audited == Counter({k: v for k, v in quality['counts'].items() if k != 'input_rows'})
print('UCI provenance, row outcomes, weekly sums, returns and eligibility reconciliation passed.')
