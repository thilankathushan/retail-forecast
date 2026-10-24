"""Minimal last-week baseline for exercising the foundation end to end."""
import hashlib
import json
import math
from pathlib import Path

import pandas as pd
from sklearn.metrics import mean_absolute_error


def read_weekly(path: Path, *, before=None) -> pd.DataFrame:
    if before is None:
        frame = pd.read_csv(path, dtype={'product_id': 'str'}, keep_default_na=False)
    else:
        chunks = pd.read_csv(path, dtype={'product_id': 'str'}, keep_default_na=False, chunksize=50000)
        frame = pd.concat([chunk[chunk.week_start.lt(before)] for chunk in chunks], ignore_index=True)
    required = {'product_id', 'week_start', 'observed_units', 'status'}
    if not required.issubset(frame.columns):
        raise ValueError(f'Weekly input requires columns {sorted(required)}; run prepare first')
    if frame.empty or frame.product_id.str.strip().eq('').any():
        raise ValueError('Weekly input must contain nonempty product IDs and rows')
    frame['week_start'] = pd.to_datetime(frame.week_start, format='%Y-%m-%d', errors='raise')
    if frame.week_start.isna().any() or frame.week_start.dt.day_of_week.ne(0).any():
        raise ValueError('week_start must be a Monday date')
    if frame.duplicated(['product_id', 'week_start']).any():
        raise ValueError('Duplicate product/week rows; regenerate weekly input')
    if not frame.status.isin(['observed', 'partial_week', 'missing_observation']).all():
        raise ValueError('Unknown weekly observation status')
    values = pd.to_numeric(frame.observed_units.replace('', float('nan')), errors='raise')
    observed = frame.status.eq('observed')
    if values[observed].isna().any() or not values[~observed].isna().all():
        raise ValueError('Observed weeks require units; incomplete weeks require blank units')
    if any(not math.isfinite(v) or v < 0 or v != int(v) for v in values[observed]):
        raise ValueError('Observed units must be finite nonnegative integers')
    frame['observed_units'] = values
    return frame.sort_values(['week_start', 'product_id'])


def backtest(frame: pd.DataFrame):
    observed = frame[frame.status.eq('observed')]
    previous = observed[['product_id', 'week_start', 'observed_units']].copy()
    previous['week_start'] += pd.Timedelta(weeks=1)
    previous = previous.rename(columns={'observed_units': 'prediction'})
    pairs = observed.merge(previous, on=['product_id', 'week_start'], validate='one_to_one')
    if pairs.empty:
        raise ValueError('No consecutive observed product/weeks; prepare more complete history')
    denominator = float(pairs.observed_units.sum())
    report = {'model': 'last_week', 'horizon_weeks': 1, 'rows': len(pairs),
              'folds': int(pairs.week_start.nunique()),
              'mae': float(mean_absolute_error(pairs.observed_units, pairs.prediction)),
              'wape': float((pairs.observed_units - pairs.prediction).abs().sum()) / denominator
              if denominator else None}
    return pairs, report


def train(frame, issue_week, config, source):
    """Fit persistence state using only the immediately preceding closed week."""
    issue = pd.Timestamp(issue_week)
    if issue.day_of_week != 0:
        raise ValueError('--issue-week must be a Monday (forecast target week start)')
    eligible = frame[frame.week_start.eq(issue - pd.Timedelta(weeks=1)) & frame.status.eq('observed')]
    if eligible.empty:
        raise ValueError('No observed sales for the previous closed week; check --issue-week and coverage')
    with source.open('rb') as stream:
        source_hash = hashlib.file_digest(stream, 'sha256').hexdigest()
    return {'schema_version': 1, 'model': 'last_week', 'issue_week': issue.date().isoformat(),
            'horizon_weeks': config.horizon_weeks, 'random_seed': config.random_seed,
            'timezone': config.timezone, 'source_sha256': source_hash,
            'predictions': {r.product_id: float(r.observed_units) for r in eligible.itertuples()}}


def forecast(path, issue_week, config):
    artifact = json.loads(path.read_text())
    if not isinstance(artifact, dict):
        raise ValueError('Invalid model artifact; run train again')
    if (artifact.get('schema_version'), artifact.get('model'), artifact.get('horizon_weeks'),
        artifact.get('timezone'), artifact.get('issue_week')) != (1, 'last_week', 1, config.timezone, issue_week):
        raise ValueError('Artifact contract or issue week mismatch; run train for this issue week')
    predictions = artifact.get('predictions')
    if not isinstance(predictions, dict) or not predictions:
        raise ValueError('Artifact has no valid predictions; run train again')
    for product, value in predictions.items():
        if not product.strip() or type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError('Invalid prediction in artifact; run train again')
    return pd.DataFrame([{'product_id': p, 'week_start': issue_week, 'prediction': v,
                          'model': 'last_week'} for p, v in sorted(predictions.items())])
