"""Offline application refit/export; never modifies frozen evaluation artifacts."""
import json
from pathlib import Path
import sys
from datetime import datetime, timezone
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from retail_forecast.baseline import read_weekly
from retail_forecast.tree import features, fit_at, predict_at, save_model
from retail_forecast.intervals import bounds, scales
from retail_forecast.source import sha256


def build(root=ROOT):
    weekly = root/'data/processed/uci/weekly.csv'
    freeze = json.loads((root/'final_freeze.json').read_text())
    calibration = json.loads((root/'interval_calibration.json').read_text())
    quality = json.loads((root/'data/processed/uci/quality.json').read_text())
    if sha256(weekly) != freeze['weekly_sha256'] or sha256(root/'interval_calibration.json') != freeze['calibration_sha256']:
        raise ValueError('Data/calibration differs from frozen versions; restore artifacts before export')
    for name, expected in freeze['code_hashes'].items():
        if sha256(root/name) != expected:
            raise ValueError(f'Frozen code differs: {name}')
    frame = read_weekly(weekly)
    origin = frame.loc[frame.status.eq('observed'), 'week_start'].max() + pd.Timedelta(weeks=1)
    protocol = freeze['protocol']
    # Exclude all partial target-week observations from fitting AND features.
    table = features(frame[frame.week_start.lt(origin)], protocol['train_start'], origin, protocol['min_history_weeks'])
    model, count = fit_at(table, origin, freeze['configuration'], freeze['seed'])
    predicted = predict_at(model, table, origin)
    out = root/'artifacts/uci/application'; out.mkdir(parents=True, exist_ok=True)
    model_path = root/'models/uci/application/tree.joblib'
    save_model(model, model_path, {'purpose':'post-evaluation application refit; not a new benchmark',
        'training_end_exclusive':origin.date().isoformat(), 'training_rows':count,
        'configuration':freeze['configuration'], 'seed':freeze['seed'],
        'weekly_file_sha256':sha256(weekly), 'freeze_sha256':sha256(root/'final_freeze.json')})
    version = sha256(model_path)
    for level in ('0.8','0.95'):
        predicted['lower_'+level], predicted['upper_'+level] = bounds(predicted.prediction, scales(predicted.mean_13), calibration['levels'][level]['quantile'])
    panel = frame[frame.week_start.lt(origin)].pivot(index='week_start', columns='product_id', values='observed_units')
    panel = panel.reindex(pd.date_range(protocol['train_start'], origin-pd.Timedelta(weeks=1), freq='7D'))
    data_hash = sha256(weekly)
    freeze_hash = sha256(root/'final_freeze.json')
    def record(row, mode):
        edge = mode == 'dataset_edge'
        week = origin if edge else pd.Timestamp(row['issue_week'])
        product = row['product_id']
        if edge:
            h = panel[product]
            seasonal = h.tail(52)
            fallback = len(seasonal) != 52 or seasonal.isna().any()
            base = {'last_observed_week':float(h.iloc[-1]), 'trailing_average':float(h.tail(4).mean()),
                    'seasonal_naive':float(h.tail(4).mean() if fallback else seasonal.iloc[0])}
        else:
            fallback = bool(row['seasonal_fallback'])
            base = {k:float(row[k]) for k in ('last_observed_week','trailing_average','seasonal_naive')}
        return {'product_id':product, 'mode':mode, 'target_week':week.date().isoformat(),
            'issue_time':week.tz_localize('Europe/London').isoformat(),
            'target_end_exclusive':(week+pd.Timedelta(weeks=1)).date().isoformat(),
            'prediction':float(row['prediction' if edge else 'tree']),
            'actual':None if edge else float(row['actual']),
            'lower_80':float(row['lower_0.8']), 'upper_80':float(row['upper_0.8']),
            'lower_95':float(row['lower_0.95']), 'upper_95':float(row['upper_0.95']),
            'baselines':base, 'seasonal_fallback':bool(fallback),
            'model_version':version if edge else freeze_hash+':'+week.date().isoformat(),
            'data_version':data_hash, 'training_cutoff_exclusive':week.date().isoformat()}
    final = pd.read_csv(root/'artifacts/uci/final/predictions.csv', dtype={'product_id':str})
    history = {}
    for product, rows in frame.groupby('product_id'):
        history[product] = [{'week':r.week_start.date().isoformat(),
            'units':float(r.observed_units) if pd.notna(r.observed_units) else None,
            'status':r.status} for r in rows.itertuples()]
    monitored = root/'artifacts/uci/monitoring/real/real'
    monitoring = {'summary':json.loads((monitored/'summary.json').read_text()),
        'events':[json.loads(line) for line in (monitored/'events.jsonl').read_text().splitlines()],
        'scores':json.loads(pd.read_csv(monitored/'scores.csv').to_json(orient='records'))}
    bundle = {'schema_version':1, 'built_at':datetime.now(timezone.utc).isoformat(),
        'coverage_start':quality['coverage_start'], 'coverage_end':quality['coverage_end'],
        'edge_week':origin.date().isoformat(), 'beyond_week':(origin+pd.Timedelta(weeks=1)).date().isoformat(),
        'data_version':data_hash, 'freeze_version':freeze_hash,
        'quality':{'assume_complete':quality['assume_complete'],
            'weekly_status_counts':frame.status.value_counts().to_dict(),
            'source_sha256':quality['source_sha256']},
        'history':history, 'forecasts':[record(r,'dataset_edge') for r in predicted.to_dict('records')]
            + [record(r,'historical') for r in final[final.scored].to_dict('records')],
        'monitoring':monitoring}
    temporary = out/'bundle.tmp'
    temporary.write_text(json.dumps(bundle,allow_nan=False,separators=(',',':')))
    temporary.replace(out/'bundle.json')
    (out/'manifest.json').write_text(json.dumps({'bundle_sha256':sha256(out/'bundle.json'),
        'model_sha256':version, 'data_sha256':data_hash, 'freeze_sha256':freeze_hash,
        'calibration_sha256':sha256(root/'interval_calibration.json'),
        'builder_sha256':sha256(Path(__file__)), 'training_cutoff_exclusive':origin.date().isoformat(),
        'edge_rows':len(predicted), 'historical_rows':int(final.scored.sum()),
        'purpose':'post-evaluation application refit, no new accuracy claim'},indent=2)+'\n')
    print(f'Saved {len(predicted)} dataset-edge forecasts and {int(final.scored.sum())} historical forecasts to {out}')

if __name__ == '__main__':
    build()
