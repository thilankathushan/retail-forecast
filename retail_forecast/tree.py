"""Global histogram trees with causal, shared training/inference features."""
import importlib.metadata
import json
import logging
from pathlib import Path
import platform
import os
os.environ.setdefault("LOKY_MAX_CPU_COUNT", "2")
import time

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from threadpoolctl import threadpool_limits

from .baseline import read_weekly
from .evaluation import load_protocol, metrics
from .source import sha256

# Frozen before the first tree run; no adaptive search.
CONFIGS = {'small': {'max_iter': 30, 'max_leaf_nodes': 7},
           'medium': {'max_iter': 60, 'max_leaf_nodes': 15}}
FEATURES = ['lag_1', 'lag_2', 'lag_4', 'lag_13', 'lag_52', 'mean_4', 'mean_13',
            'std_4', 'history_observed', 'history_active', 'activity_fraction', 'history_age',
            'month', 'week_sin', 'week_cos']
LOG = logging.getLogger(__name__)


def features(frame, start, end, minimum=4):
    """Each row describes its OWN origin. end is inclusive, targets never features."""
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    frame = frame[frame.week_start.ge(start) & frame.week_start.le(end)]
    panel = frame.pivot(index='week_start', columns='product_id', values='observed_units')
    panel = panel.reindex(pd.date_range(start, end, freq='7D'))
    prior = panel.shift(1)
    observed = panel.notna().cumsum().shift(1, fill_value=0)
    active = panel.gt(0).cumsum().shift(1, fill_value=0)
    seen = panel.notna().cummax().shift(1, fill_value=False)
    age = seen.cumsum()
    arrays = {f'lag_{lag}': panel.shift(lag) for lag in [1, 2, 4, 13, 52]}
    arrays.update(mean_4=prior.rolling(4, min_periods=4).mean(),
                  mean_13=prior.rolling(13, min_periods=1).mean(),
                  std_4=prior.rolling(4, min_periods=4).std(ddof=0),
                  history_observed=observed, history_active=active,
                  activity_fraction=active / observed.replace(0, np.nan), history_age=age)
    index = pd.MultiIndex.from_product([panel.index, panel.columns], names=['week_start', 'product_id'])
    result = pd.DataFrame({k: v.to_numpy().ravel() for k, v in arrays.items()}, index=index)
    dates = result.index.get_level_values('week_start')
    result['month'] = dates.month
    week = dates.isocalendar().week.to_numpy(dtype=float)
    result['week_sin'] = np.sin(2*np.pi*week/52)
    result['week_cos'] = np.cos(2*np.pi*week/52)
    result['eligible'] = prior.notna().rolling(minimum, min_periods=minimum).sum().eq(minimum).to_numpy().ravel()
    result['actual'] = panel.to_numpy().ravel()
    return result.reset_index()


def estimator(configuration, seed=42):
    # No randomized validation split. Native NaN handling and learned bins fit per fold.
    return Pipeline([('missing', SimpleImputer(strategy='constant', fill_value=-1, add_indicator=True, keep_empty_features=True)), ('tree', HistGradientBoostingRegressor(loss='absolute_error', learning_rate=0.1,
                     min_samples_leaf=20, early_stopping=False, random_state=seed, **configuration))])


def fit_at(table, origin, configuration, seed=42):
    train = table[table.week_start.lt(pd.Timestamp(origin)) & table.eligible & table.actual.notna()]
    if train.empty:
        raise ValueError('No eligible historical training examples at this origin')
    model = estimator(configuration, seed)
    with threadpool_limits(limits=2):
        model.fit(train[FEATURES], train.actual)
    return model, len(train)


def predict_at(model, table, origin):
    target = table[table.week_start.eq(pd.Timestamp(origin)) & table.eligible].copy()
    if target.empty:
        raise ValueError('No products have sufficient observed history at this origin')
    with threadpool_limits(limits=2):
        target['prediction'] = np.maximum(0, model.predict(target[FEATURES]))
    return target


def dependencies():
    return {name: importlib.metadata.version(name) for name in ['scikit-learn', 'pandas', 'numpy', 'scipy', 'joblib']}


def save_model(model, path, metadata):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, path)
    metadata = metadata | {'schema_version': 1, 'features': FEATURES, 'dependencies': dependencies(),
                           'python': platform.python_version(), 'model_sha256': sha256(path)}
    path.with_suffix('.json').write_text(json.dumps(metadata, indent=2) + '\n')


def reload_model(path):
    path = Path(path)
    meta = json.loads(path.with_suffix('.json').read_text())
    if meta['features'] != FEATURES or meta['schema_version'] != 1 or meta['dependencies'] != dependencies():
        raise ValueError('Model schema or dependency mismatch; retrain in this environment')
    if meta['model_sha256'] != sha256(path):
        raise ValueError('Model hash mismatch; restore the matching local artifact')
    return joblib.load(path), meta  # Only locally produced, trusted artifacts.


def forecast_saved(weekly, artifact, origin):
    model, meta = reload_model(artifact)
    origin = pd.Timestamp(origin)
    if origin.day_of_week != 0 or origin < pd.Timestamp(meta['training_end_exclusive']):
        raise ValueError('Issue week must be Monday and not precede the training cutoff')
    if origin >= pd.Timestamp(meta['protocol']['holdout_start']):
        raise ValueError('Final holdout is reserved; tree forecasting into it is disabled')
    if sha256(weekly) != meta['weekly_file_sha256']:
        raise ValueError('Weekly data version differs from artifact; retrain/version explicitly')
    frame = read_weekly(weekly, before=origin.date().isoformat())
    table = features(frame, meta['protocol']['train_start'], origin, meta['protocol']['min_history_weeks'])
    result = predict_at(model, table, origin)
    result['issued_at'] = origin.tz_localize('Europe/London').isoformat()
    return result[['product_id', 'week_start', 'issued_at', 'prediction']]


def run_tree(weekly, protocol_path, output, model_path, baseline_dir):
    begin = time.perf_counter()
    protocol = load_protocol(protocol_path)
    base = json.loads((baseline_dir / 'metrics.json').read_text())
    if base['protocol_sha256'] != sha256(protocol_path) or base['weekly_file_sha256'] != sha256(weekly):
        raise ValueError('Baseline artifacts mismatch protocol/data; rerun development baselines')
    frame = read_weekly(weekly, before=protocol['holdout_start'])
    end = pd.Timestamp(protocol['holdout_start']) - pd.Timedelta(weeks=1)
    table = features(frame, protocol['train_start'], end, protocol['min_history_weeks'])
    baseline = pd.read_csv(baseline_dir / 'predictions.csv', dtype={'product_id': str})
    reference = baseline[baseline.model.eq('last_observed_week') & baseline.scored].copy()
    expected = set(zip(reference.issue_week, reference.product_id))
    output.mkdir(parents=True, exist_ok=True)
    results, summaries, timings, failures = [], {}, [], []
    for name, configuration in CONFIGS.items():
        parts = []
        for origin in pd.date_range(protocol['development_start'], end, freq='7D'):
            tick = time.perf_counter()
            try:
                model, count = fit_at(table, origin, configuration)
                fit_seconds = time.perf_counter()-tick
                predicted = predict_at(model, table, origin)
                predicted['issue_week'] = origin.date().isoformat()
                predicted['model'] = name
                predicted['scored'] = predicted.actual.notna()
                parts.append(predicted[['issue_week', 'product_id', 'model', 'actual', 'prediction', 'scored']])
                timings.append({'model': name, 'issue_week': origin.date().isoformat(), 'training_rows': count,
                                'fit_seconds': fit_seconds, 'total_seconds': time.perf_counter()-tick})
                LOG.info('%s origin %s completed in %.2fs', name, origin.date(), time.perf_counter()-tick)
            except Exception as exc:
                failures.append({'model': name, 'issue_week': origin.date().isoformat(), 'error': str(exc)})
                (output/'failures.json').write_text(json.dumps(failures, indent=2))
                raise  # Never compare a candidate that skipped failed/difficult folds.
        predictions = pd.concat(parts, ignore_index=True)
        scored = predictions[predictions.scored]
        if set(zip(scored.issue_week, scored.product_id)) != expected or len(scored) != len(expected):
            raise ValueError('Tree and baseline scored cohorts differ; comparison aborted')
        summaries[name] = metrics(scored.actual, scored.prediction)
        summaries[name]['fit_predict_seconds'] = sum(r['total_seconds'] for r in timings if r['model'] == name)
        results.append(predictions)
    selected = min(summaries, key=lambda name: (summaries[name]['mae'], name))
    # Persist last development origin's refit, permitting an offline reload/replay
    # without forecasting any holdout target.
    model, count = fit_at(table, end, CONFIGS[selected])
    metadata = {'selected': selected, 'configuration': CONFIGS[selected], 'seed': 42,
                'training_end_exclusive': end.date().isoformat(), 'training_rows': count,
                'protocol': protocol, 'protocol_sha256': sha256(protocol_path),
                'weekly_file_sha256': sha256(weekly), 'feature_code_sha256': sha256(Path(__file__)),
                'source_csv_sha256': protocol['source_csv_sha256'], 'selection': 'minimum pooled development MAE; tie by name'}
    save_model(model, model_path, metadata)
    combined = pd.concat(results, ignore_index=True)
    combined.to_csv(output/'predictions.csv', index=False)
    pd.DataFrame(timings).to_csv(output/'timings.csv', index=False)
    per_product = [dict(model=m, product_id=p, **metrics(g.actual, g.prediction))
                   for (m,p),g in combined[combined.scored].groupby(['model','product_id'])]
    pd.DataFrame(per_product).to_csv(output/'per_product.csv', index=False)
    report = {'selected': selected, 'candidates': summaries, 'baseline_metrics': base['models'],
              'coverage': base['coverage'], 'failures': failures, 'holdout_evaluated': False,
              'configurations': CONFIGS, 'total_seconds': time.perf_counter()-begin,
              'metadata': metadata}
    (output/'metrics.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    (output/'failures.json').write_text(json.dumps(failures)+'\n')
    return report
