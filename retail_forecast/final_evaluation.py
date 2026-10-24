"""Freeze historical calibration, then execute one auditable final evaluation."""
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import platform
import time

import numpy as np
import pandas as pd

from .baseline import read_weekly
from .evaluation import load_protocol, metrics
from .intervals import LEVELS, bounds, calibrate, interval_metrics, scales
from .source import sha256
from .tree import CONFIGS, FEATURES, dependencies, features, fit_at, predict_at

LOG = logging.getLogger(__name__)
MODELS = ('tree', 'last_observed_week', 'trailing_average', 'seasonal_naive')
SEGMENTS = ('history_segment', 'scale_segment', 'activity_segment')
CODE_FILES = ('retail_forecast/tree.py', 'retail_forecast/intervals.py',
              'retail_forecast/final_evaluation.py', 'retail_forecast/evaluation.py',
              'retail_forecast/baseline.py')


def write_json(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def freeze(weekly, protocol_path, devdir, freeze_path):
    freeze_path = Path(freeze_path)
    if freeze_path.exists():
        raise ValueError('Freeze already exists; retain it. Changes require a new exploratory version.')
    protocol = load_protocol(protocol_path)
    report = json.loads((devdir/'metrics.json').read_text())
    if report['metadata']['weekly_file_sha256'] != sha256(weekly) or report['metadata']['protocol_sha256'] != sha256(protocol_path):
        raise ValueError('Development data/protocol mismatch')
    if report['metadata']['feature_code_sha256'] != sha256('retail_forecast/tree.py'):
        raise ValueError('Selected-model feature code changed since development')
    selected = report['selected']
    frame = read_weekly(weekly, before=protocol['holdout_start'])
    table = features(frame, protocol['train_start'], pd.Timestamp(protocol['holdout_start'])-pd.Timedelta(weeks=1))
    pred = pd.read_csv(devdir/'predictions.csv', dtype={'product_id':str})
    pred = pred[pred.model.eq(selected) & pred.scored].copy()
    if not pred.issue_week.ge(protocol['development_start']).all() or not pred.issue_week.lt(protocol['holdout_start']).all():
        raise ValueError('Calibration contains non-development dates')
    pred['week_start'] = pd.to_datetime(pred.issue_week)
    scores = pred.merge(table[['week_start','product_id','mean_13','actual']],
                        on=['week_start','product_id'],validate='one_to_one',suffixes=('','_check'))
    if len(scores) != len(pred) or not np.array_equal(scores.actual,scores.actual_check):
        raise ValueError('Development residuals do not align with the versioned weekly data')
    scores['scale'] = scales(scores.mean_13)
    scores['normalized_absolute_error'] = abs(scores.actual-scores.prediction)/scores.scale
    calibration = calibrate(scores.actual,scores.prediction,scores.scale)
    calibration.update({'selected_model':selected,'development_prediction_sha256':sha256(devdir/'predictions.csv'),
                        'start':protocol['development_start'],'end_exclusive':protocol['holdout_start'],
                        'uses_holdout_outcomes':False})
    calibration_path = freeze_path.with_name('interval_calibration.json')
    write_json(calibration_path,calibration)
    (devdir/'calibration_scores.csv').parent.mkdir(parents=True,exist_ok=True)
    scores.to_csv(devdir/'calibration_scores.csv',index=False)
    specification = {'schema_version':1,'frozen_at_utc':datetime.now(timezone.utc).isoformat(),
                     'protocol':protocol,'features':FEATURES,'selected_model':selected,
                     'configuration':CONFIGS[selected], 'seed':42,'cpu_threads':2,
                     'retraining':'weekly expanding history; targets strictly before origin',
                     'interval_updates':'none during holdout','levels':list(LEVELS),
                     'scale':'max(1, prior mean13 available weeks)',
                     'segment_rules':{'history':[0,4,13,52],'scale':[5,25],'activity':'all_zero vs previously_positive'},
                     'metrics':['mae','aggregate_wape','interval_coverage','mean_width','median_width','mean_interval_score'],
                     'dependencies':dependencies(),'python':platform.python_version(),
                     'weekly_sha256':sha256(weekly),'protocol_sha256':sha256(protocol_path),
                     'calibration_sha256':sha256(calibration_path),
                     'code_hashes':{p:sha256(p) for p in CODE_FILES},
                     'declaration_sha256':sha256('FINAL_EVALUATION.md')}
    write_json(freeze_path,specification)
    LOG.info('Frozen final procedure and %s historical OOS calibration scores; no holdout loaded',len(scores))
    return specification


def segment(table):
    result = table.copy()
    h = result.history_observed
    result['history_segment'] = np.select([h.eq(0),h.lt(4),h.lt(13),h.lt(52)],
                                          ['0','1-3','4-12','13-51'],default='52+')
    s = result.mean_13.fillna(0).clip(lower=1)
    result['scale'] = s
    result['scale_segment'] = np.select([s.le(5),s.le(25)],['<=5','5-25'],default='>25')
    result['activity_segment'] = np.where(result.history_active.eq(0),'all_zero','previously_positive')
    return result


def forecast_origin(history, origin, spec):
    origin = pd.Timestamp(origin)
    if history.week_start.ge(origin).any():
        raise ValueError('History includes target/future observations')
    p = spec['protocol']
    start = time.perf_counter()
    table = features(history,p['train_start'],origin,p['min_history_weeks'])
    feature_seconds = time.perf_counter()-start
    tick = time.perf_counter()
    model,ntrain = fit_at(table,origin,spec['configuration'],spec['seed'])
    fit_seconds = time.perf_counter()-tick
    tick = time.perf_counter()
    target = predict_at(model,table,origin)
    predict_seconds = time.perf_counter()-tick
    target = segment(target)
    tick = time.perf_counter()
    panel = history[history.week_start.ge(p['train_start'])].pivot(index='week_start',columns='product_id',values='observed_units')
    panel = panel.reindex(pd.date_range(p['train_start'],origin-pd.Timedelta(weeks=1),freq='7D'))
    seasonal = panel.tail(p['seasonal_weeks'])
    available = seasonal.notna().sum().eq(p['seasonal_weeks'])
    target['seasonal_fallback'] = ~target.product_id.map(available).fillna(False)
    target['last_observed_week'] = target.lag_1
    target['trailing_average'] = target.mean_4
    target['seasonal_naive'] = np.where(target.seasonal_fallback,target.mean_4,
                                       target.product_id.map(seasonal.iloc[0]))
    target['tree'] = target.prediction
    baseline_seconds = time.perf_counter()-tick
    metadata = segment(table[table.week_start.eq(origin)])
    return target,metadata,{'feature_seconds':feature_seconds,'fit_seconds':fit_seconds,
                           'tree_inference_seconds':predict_seconds,'baseline_inference_seconds':baseline_seconds,
                           'training_rows':ntrain}


def execute(weekly, freeze_path, output):
    freeze_path,output = Path(freeze_path),Path(output)
    spec = json.loads(freeze_path.read_text())
    calibration_path = freeze_path.with_name('interval_calibration.json')
    if spec['weekly_sha256']!=sha256(weekly) or spec['calibration_sha256']!=sha256(calibration_path):
        raise ValueError('Frozen data/calibration hash mismatch')
    if spec['dependencies']!=dependencies() or any(sha256(p)!=v for p,v in spec['code_hashes'].items()):
        raise ValueError('Code/dependencies differ from freeze; do not call changed work a pristine final test')
    if output.exists():
        raise ValueError('Final run directory already exists. Holdout is exposed; any later run must be exploratory.')
    output.mkdir(parents=True)
    write_json(output/'STARTED.json',{'freeze_sha256':sha256(freeze_path),'started_at_utc':datetime.now(timezone.utc).isoformat(),
                                    'warning':'Final holdout is now exposed. Later changes are exploratory.'})
    calibration = json.loads(calibration_path.read_text())
    p = spec['protocol']
    began = time.perf_counter()
    frame = read_weekly(weekly,before=p['holdout_end_exclusive'])
    predictions,audits,timings = [],[],[]
    for origin in pd.date_range(p['holdout_start'],pd.Timestamp(p['holdout_end_exclusive'])-pd.Timedelta(weeks=1),freq='7D'):
        tick = time.perf_counter()
        history = frame[frame.week_start.lt(origin)]
        target,meta,runtime = forecast_origin(history,origin,spec)
        # Only after forecasting do we join this week's outcomes for scoring.
        truth = frame[frame.week_start.eq(origin)][['product_id','observed_units']]
        target = target.merge(truth,on='product_id',how='left',validate='one_to_one')
        target['actual'] = target.observed_units
        target['scored'] = target.actual.notna()
        target['issue_week'] = origin.date().isoformat()
        target['issued_at'] = origin.tz_localize(p['timezone']).isoformat()
        for level in spec['levels']:
            lo,hi = bounds(target.tree,target.scale,calibration['levels'][str(level)]['quantile'])
            target[f'lower_{level}'],target[f'upper_{level}'] = lo,hi
        keep = ['issue_week','issued_at','product_id','actual','scored','scale',*SEGMENTS,'seasonal_fallback',*MODELS]
        keep += [f'{side}_{level}' for level in spec['levels'] for side in ('lower','upper')]
        predictions.append(target[keep])
        meta = meta[['product_id','history_observed','eligible',*SEGMENTS]].merge(truth,on='product_id',how='outer')
        meta['history_status'] = np.select([meta.history_observed.isna(),meta.history_observed.fillna(0).lt(p['min_history_weeks']),
                                            ~meta.eligible.fillna(False).astype(bool)],
                                           ['new_product','short_history','incomplete_recent_history'],default='eligible')
        for column in SEGMENTS:
            meta[column] = meta[column].fillna('new_product')
        meta['target_observed'] = meta.observed_units.notna()
        meta['scored'] = meta.history_status.eq('eligible') & meta.target_observed
        meta['issue_week'] = origin.date().isoformat()
        audits.append(meta.drop(columns='observed_units'))
        runtime.update(issue_week=origin.date().isoformat(),total_seconds=time.perf_counter()-tick)
        timings.append(runtime)
        LOG.info('Frozen final origin %s completed; training rows %s',origin.date(),runtime['training_rows'])
    pred = pd.concat(predictions,ignore_index=True)
    audit = pd.concat(audits,ignore_index=True)
    pred.to_csv(output/'predictions.csv',index=False)
    audit.to_csv(output/'eligibility.csv',index=False)
    pd.DataFrame(timings).to_csv(output/'runtime.csv',index=False)
    scored = pred[pred.scored]
    point = {model:metrics(scored.actual,scored[model]) for model in MODELS}
    intervals = {str(level):interval_metrics(scored.actual,scored[f'lower_{level}'],scored[f'upper_{level}'],level) for level in spec['levels']}
    # Segments and per-product tables retain row counts; no mean-of-WAPE aggregation.
    for dimension in (*SEGMENTS,'product_id','issue_week'):
        rows=[]
        for value,group in scored.groupby(dimension):
            for model in MODELS:
                rows.append({dimension:value,'model':model,**metrics(group.actual,group[model])})
        pd.DataFrame(rows).to_csv(output/f'point_by_{dimension}.csv',index=False)
        rows=[]
        for value,group in scored.groupby(dimension):
            for level in spec['levels']:
                rows.append({dimension:value,'level':level,**interval_metrics(group.actual,group[f'lower_{level}'],group[f'upper_{level}'],level)})
        pd.DataFrame(rows).to_csv(output/f'interval_by_{dimension}.csv',index=False)
    coverage=[]
    for dimension in SEGMENTS:
        for value,g in audit.groupby(dimension):
            coverage.append({'dimension':dimension,'segment':value,'candidates':len(g),'scored':int(g.scored.sum()),
                             'coverage':float(g.scored.mean()),'exclusions':g.loc[~g.scored,'history_status'].value_counts().to_dict()})
    report={'status':'final_holdout_evaluated','freeze_sha256':sha256(freeze_path),'point':point,'intervals':intervals,
            'coverage':{'candidates':len(audit),'scored':len(scored),'fraction':len(scored)/len(audit),
                        'history_status_counts':audit.history_status.value_counts().to_dict(),
                        'eligible_missing_target':int((audit.history_status.eq('eligible') & ~audit.target_observed).sum()),
                        'seasonal_fallback_scored':int(scored.seasonal_fallback.sum())},
            'segment_coverage':coverage,'runtime_totals':pd.DataFrame(timings).select_dtypes('number').sum().to_dict(),
            'total_seconds':time.perf_counter()-began,
            'measurement_conditions':{'machine':platform.machine(),'platform':platform.platform(),'python':platform.python_version(),
                                      'dependencies':dependencies(),'threads':2,'folds':'sequential; weekly retraining',
                                      'timing':'wall-clock perf_counter; feature, fit, predict and baseline timing separate; no hyperparameter search'},
            'holdout_reuse_policy':'Any later model/method changes are exploratory; holdout is no longer untouched.'}
    write_json(output/'metrics.json',report)
    write_json(output/'COMPLETED.json',{'completed_at_utc':datetime.now(timezone.utc).isoformat(),'predictions_sha256':sha256(output/'predictions.csv')})
    return report
