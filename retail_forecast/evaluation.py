"""Frozen chronological development evaluation; no holdout execution path."""
import json
from pathlib import Path

import pandas as pd

from .source import sha256

MODELS = ('last_observed_week', 'trailing_average', 'seasonal_naive')


def load_protocol(path):
    protocol = json.loads(Path(path).read_text())
    for key in ('train_start', 'development_start', 'holdout_start', 'holdout_end_exclusive'):
        value = pd.Timestamp(protocol[key])
        if value.day_of_week != 0 or value != value.normalize() or value.tzinfo:
            raise ValueError(f'{key} must be a naive Monday date')
    dates = [pd.Timestamp(protocol[k]) for k in ('train_start', 'development_start', 'holdout_start', 'holdout_end_exclusive')]
    if not all(a < b for a, b in zip(dates, dates[1:])):
        raise ValueError('Protocol date ranges must be strictly chronological')
    for key in ('min_history_weeks', 'trailing_weeks', 'seasonal_weeks'):
        if type(protocol[key]) is not int or protocol[key] < 1:
            raise ValueError(f'{key} must be a positive integer')
    if protocol['min_history_weeks'] < protocol['trailing_weeks']:
        raise ValueError('Minimum history must cover the trailing window')
    if protocol['horizon_weeks'] != 1 or protocol['seasonal_fallback'] != 'trailing_average':
        raise ValueError('Only one-week forecasts with trailing-average seasonal fallback are supported')
    if protocol['timezone'] != 'Europe/London':
        raise ValueError('Expected Europe/London timezone')
    return protocol


def folds(protocol):
    rows = []
    for split, start, end in [('development', protocol['development_start'], protocol['holdout_start']),
                              ('holdout', protocol['holdout_start'], protocol['holdout_end_exclusive'])]:
        for origin in pd.date_range(start, pd.Timestamp(end) - pd.Timedelta(weeks=1), freq='7D'):
            rows.append({'split': split, 'issue_week': origin.date().isoformat(),
                         'issued_at': origin.tz_localize(protocol['timezone']).isoformat(),
                         'train_start': protocol['train_start'],
                         'train_end_exclusive': origin.date().isoformat(),
                         'target_end_exclusive': (origin + pd.Timedelta(weeks=1)).date().isoformat(),
                         'executed': split == 'development'})
    return pd.DataFrame(rows)


def metrics(actual, predicted):
    actual, predicted = list(actual), list(predicted)
    import math
    if len(actual) != len(predicted) or any(not math.isfinite(x) or x < 0 for x in actual + predicted):
        raise ValueError('Metrics require aligned finite nonnegative actuals and predictions')
    errors = [abs(a - p) for a, p in zip(actual, predicted)]
    total = float(sum(actual))
    absolute = float(sum(errors))
    return {'rows': len(actual), 'actual_units': total, 'absolute_error': absolute,
            'mae': absolute / len(actual) if actual else None,
            'wape': absolute / total if total else None}


def evaluate_development(frame, protocol):
    """Eligibility/prediction use strictly earlier rows; target access is separate."""
    start = pd.Timestamp(protocol['train_start'])
    stop = pd.Timestamp(protocol['holdout_start'])
    frame = frame[frame.week_start.ge(start) & frame.week_start.lt(stop)].copy()
    panel = frame.pivot(index='week_start', columns='product_id', values='observed_units')
    calendar = pd.date_range(start, stop - pd.Timedelta(weeks=1), freq='7D')
    panel = panel.reindex(calendar)
    present = frame.groupby('product_id').week_start.min()
    predictions, audit = [], []
    definitions = folds(protocol)
    for fold in definitions[definitions.split.eq('development')].itertuples():
        origin = pd.Timestamp(fold.issue_week)
        past = panel.loc[panel.index < origin]
        # Columns are a storage convenience; future-only products never become candidates.
        candidates = sorted(present[present.le(origin)].index)
        minimum = protocol['min_history_weeks']
        for product in candidates:
            history = past[product]
            prior = history.dropna()
            recent = history.tail(minimum)
            target = panel.at[origin, product]
            if present[product] == origin:
                reason = 'new_product'
            elif len(prior) < minimum:
                reason = 'short_history'
            elif len(recent) < minimum or recent.isna().any():
                reason = 'incomplete_recent_history'
            else:
                reason = 'eligible'
            eligible = reason == 'eligible'
            score = eligible and pd.notna(target)
            all_zero = bool(len(prior) and prior.eq(0).all())
            audit.append({'issue_week': fold.issue_week, 'product_id': product,
                          'history_status': reason, 'prior_observations': len(prior),
                          'all_zero_history': all_zero, 'target_observed': pd.notna(target),
                          'scored': score})
            if not eligible:
                continue
            trailing = float(history.tail(protocol['trailing_weeks']).mean())
            seasonal_history = history.tail(protocol['seasonal_weeks'])
            seasonal_available = len(seasonal_history) == protocol['seasonal_weeks'] and seasonal_history.notna().all()
            values = [float(prior.iloc[-1]), trailing,
                      float(seasonal_history.iloc[0]) if seasonal_available else trailing]
            for model, value in zip(MODELS, values):
                predictions.append({'issue_week': fold.issue_week, 'issued_at': fold.issued_at,
                                    'target_end_exclusive': fold.target_end_exclusive,
                                    'product_id': product, 'model': model, 'prediction': value,
                                    'actual': float(target) if pd.notna(target) else None, 'scored': score,
                                    'all_zero_history': all_zero,
                                    'seasonal_fallback': model == 'seasonal_naive' and not seasonal_available})
    pred = pd.DataFrame(predictions, columns=['issue_week', 'issued_at', 'target_end_exclusive', 'product_id',
                                            'model', 'prediction', 'actual', 'scored', 'all_zero_history', 'seasonal_fallback'])
    audit = pd.DataFrame(audit, columns=['issue_week', 'product_id', 'history_status', 'prior_observations',
                                       'all_zero_history', 'target_observed', 'scored'])
    return pred, audit, definitions


def summarize(predictions, audit):
    scored = predictions[predictions.scored.eq(True)]
    report = {'split': 'development', 'holdout_evaluated': False, 'models': {},
              'coverage': {'candidate_product_weeks': len(audit),
                           'history_status_counts': audit.history_status.value_counts().to_dict(),
                           'target_observed': int(audit.target_observed.sum()),
                           'scored_product_weeks': int(audit.scored.sum()),
                           'eligible_missing_target': int((audit.history_status.eq('eligible') & ~audit.target_observed).sum()),
                           'scored_all_zero_history': int((audit.scored & audit.all_zero_history).sum())}}
    total = report['coverage']['candidate_product_weeks']
    report['coverage']['scored_fraction'] = int(audit.scored.sum()) / total if total else None
    for model in MODELS:
        group = scored[scored.model.eq(model)]
        report['models'][model] = metrics(group.actual, group.prediction)
        report['models'][model]['seasonal_fallback_rows'] = int(group.seasonal_fallback.sum())
    return report


def run_development(weekly, protocol_path, output_dir):
    from .baseline import read_weekly
    protocol = load_protocol(protocol_path)
    quality_path = Path(weekly).with_name('quality.json')
    quality = json.loads(quality_path.read_text())
    if quality['source_sha256'] != protocol['source_csv_sha256']:
        raise ValueError('Prepared source differs from frozen protocol; explicitly version a new protocol')
    if (pd.Timestamp(quality['coverage_start']) > pd.Timestamp(protocol['train_start']) or
            pd.Timestamp(quality['coverage_end']) < pd.Timestamp(protocol['holdout_end_exclusive']) - pd.Timedelta(days=1)):
        raise ValueError('Prepared coverage does not contain the frozen complete-week ranges')
    frame = read_weekly(weekly, before=protocol['holdout_start'])
    pred, audit, definitions = evaluate_development(frame, protocol)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report = summarize(pred, audit)
    report.update({'protocol_sha256': sha256(protocol_path), 'weekly_file_sha256': sha256(weekly),
                   'prepared_quality_sha256': sha256(quality_path),
                   'coverage_assumption': quality.get('assume_complete'),
                   'protocol': protocol, 'zero_denominator_policy': 'WAPE null when sum actual is zero; MAE remains defined for nonempty rows'})
    pred.to_csv(output_dir / 'predictions.csv', index=False)
    audit.to_csv(output_dir / 'eligibility.csv', index=False)
    definitions.to_csv(output_dir / 'folds.csv', index=False)
    for keys, filename in [(['model', 'product_id'], 'per_product.csv'), (['model', 'issue_week'], 'per_fold.csv')]:
        rows = []
        for identity, group in pred[pred.scored.eq(True)].groupby(keys):
            rows.append(dict(zip(keys, identity)) | metrics(group.actual, group.prediction))
        pd.DataFrame(rows).to_csv(output_dir / filename, index=False)
    (output_dir / 'metrics.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report
