"""Simulated delivery/forecast monitoring; never a new final-model evaluation."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3

import numpy as np
import pandas as pd

from .source import sha256
from .evaluation import metrics
from .intervals import interval_metrics


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False,
                      default=lambda x:x.item() if hasattr(x,'item') else str(x))


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def utc(value):
    stamp=pd.Timestamp(value)
    if stamp.tzinfo is None:raise ValueError('Availability/issue clocks must include a timezone')
    return stamp.tz_convert('UTC')


def week_close(week):
    return (pd.Timestamp(week)+pd.Timedelta(days=7)).tz_localize('Europe/London').tz_convert('UTC')


def frame_version(frame):
    return hashlib.sha256(frame.to_csv(index=False).encode()).hexdigest()


def validate_delivery(frame,week):
    required={'product_id','week_start','observed_units','status'}
    if not required.issubset(frame.columns):return 'schema_failure',{'missing_columns':sorted(required-set(frame.columns))}
    if frame.empty:return 'missing_data',{'rows':0}
    values=pd.to_numeric(frame.observed_units,errors='coerce')
    if (frame.product_id.astype(str).str.strip().eq('').any() or frame.product_id.isna().any() or
        frame.product_id.duplicated().any() or not frame.week_start.eq(week).all() or
        not frame.status.eq('observed').all() or values.isna().any() or
        not np.isfinite(values).all() or values.lt(0).any() or values.mod(1).ne(0).any()):
        return 'data_quality_failure',{'reason':'empty/duplicate ID, wrong week, uncertain target, or invalid units'}
    return None,{}


class Ledger:
    """One transaction per replay; uniqueness plus payload checks makes retries safe."""
    def __init__(self,path):
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(path,timeout=60)
        self.db.execute('CREATE TABLE IF NOT EXISTS entries (stream TEXT, kind TEXT, entry_key TEXT, payload TEXT, PRIMARY KEY(stream,kind,entry_key))')
        self.db.commit()
        self.db.execute('BEGIN IMMEDIATE')

    def put(self,stream,kind,key,payload):
        encoded=canonical(payload)
        row=self.db.execute('SELECT payload FROM entries WHERE stream=? AND kind=? AND entry_key=?',(stream,kind,key)).fetchone()
        if row:
            if row[0]!=encoded:raise ValueError(f'Conflicting {kind} for {stream}/{key}; use an explicit new version/stream')
            return False
        self.db.execute('INSERT INTO entries VALUES (?,?,?,?)',(stream,kind,key,encoded))
        return True

    def finish(self,success):
        self.db.commit() if success else self.db.rollback()
        self.db.close()


def replay(deliveries,forecasts,rules,output,stream,kind,source_refs,as_of=None):
    """Deliveries become visible at available_at. Clock events are processed in order.

    Archived forecasts are admitted only if the preceding week's complete delivery
    is available at their original issue time. Rejected forecasts are not backdated.
    """
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    arrivals={}
    weeks=set()
    for delivery in deliveries:
        stamp=utc(delivery['available_at']);week=delivery['week']
        if stamp<week_close(week):raise ValueError('A completed-week delivery cannot arrive before its week closes')
        arrivals.setdefault(stamp,[]).append(delivery);weeks.add(week)
    forecasts=forecasts.copy()
    required={'product_id','target_week','issue_time','prediction','lower_80','upper_80','lower_95','upper_95','model_version','data_version'}
    if not required.issubset(forecasts.columns):raise ValueError('Forecast batch schema incomplete')
    numeric=forecasts[['prediction','lower_80','upper_80','lower_95','upper_95']].to_numpy(dtype=float)
    if not np.isfinite(numeric).all() or (numeric<0).any():raise ValueError('Invalid forecast numbers')
    for level in (80,95):
        if not (forecasts[f'lower_{level}'].le(forecasts.prediction)&forecasts[f'upper_{level}'].ge(forecasts.prediction)).all():raise ValueError('Invalid forecast interval bounds')
    if forecasts.duplicated(['target_week','product_id']).any():raise ValueError('Duplicate forecast keys in batch')
    issues={}
    for stamp,group in forecasts.groupby('issue_time'):
        timestamp=utc(stamp)
        for week in group.target_week.unique():
            if timestamp!=pd.Timestamp(week).tz_localize('Europe/London').tz_convert('UTC'):
                raise ValueError('Archived issue time must match local Monday target start')
        issues[timestamp]=group
        weeks.update(group.target_week)
    deadlines={week_close(w)+pd.Timedelta(hours=rules['late_after_hours']):w for w in weeks}
    clocks=sorted(set(arrivals)|set(issues)|set(deadlines))
    limit=utc(as_of) if as_of else max(clocks)
    manifest={'simulation':True,'kind':kind,'stream':stream,'rules':rules,'source_refs':source_refs,
              'monitor_code_sha256':sha256(__file__),
              'delivery_versions':[{'week':d['week'],'available_at':utc(d['available_at']).isoformat(),'sha256':frame_version(d['frame'])} for d in deliveries],
              'forecast_source_sha256':frame_version(forecasts)}
    ledger=Ledger(output/'ledger.sqlite')
    accepted,persisted,scores,events={}, {}, {}, []
    snapshots={};series=[];forecast_records=[]
    def event(clock,week,name,severity,detail):
        record={'at':clock.isoformat(),'week':week,'event':name,'severity':severity,'detail':detail,'simulated':True}
        ledger.put(stream,'event',f'{clock.isoformat()}:{week}:{name}',record);events.append(record)
    success=False
    try:
        prior_events=ledger.db.execute("SELECT payload FROM entries WHERE stream=? AND kind='event'",(stream,)).fetchall()
        if prior_events and max(utc(json.loads(r[0])['at']) for r in prior_events)>limit:
            raise ValueError('Cannot rewind an already processed stream; use a separate replay stream')
        ledger.put(stream,'manifest','version',manifest)
        for clock in clocks:
            if clock>limit:break
            for delivery in arrivals.get(clock,[]):
                week=delivery['week'];frame=delivery['frame'];version=frame_version(frame)
                reason,detail=validate_delivery(frame,week)
                if clock>week_close(week)+pd.Timedelta(hours=rules['late_after_hours']):
                    event(clock,week,'late_data','warning',{'hours_after_close':(clock-week_close(week)).total_seconds()/3600})
                if reason:
                    event(clock,week,reason,'error',detail);continue
                prior_weeks=sorted(w for w in snapshots if w<week)
                previous=snapshots[prior_weeks[-1]] if prior_weeks else None
                if previous is not None:
                    missing=set(previous.product_id)-set(frame.product_id)
                    if len(missing)>rules['missing_expected_product_tolerance']:
                        event(clock,week,'dropped_product_records','error',{'count':len(missing),'expected_prior_products':len(previous)})
                        continue
                    prior_mean=float(previous.observed_units.mean());current_mean=float(frame.observed_units.mean())
                    ratio=(current_mean+1)/(prior_mean+1)
                    activity_change=float(frame.observed_units.gt(0).mean()-previous.observed_units.gt(0).mean())
                    if ratio<rules['sales_mean_ratio_low'] or ratio>rules['sales_mean_ratio_high']:
                        event(clock,week,'sales_distribution_signal','investigate',{'smoothed_mean_ratio':ratio,'meaning':'not proof of model failure'})
                    if abs(activity_change)>=rules['activity_fraction_change']:
                        event(clock,week,'product_activity_signal','investigate',{'active_fraction_change':activity_change})
                if week in accepted and accepted[week]['version']!=version:
                    raise ValueError('A previously accepted observation was revised; explicit revision handling/new stream required')
                snapshots[week]=frame
                accepted[week]={'frame':frame,'version':version,'available_at':clock}
                event(clock,week,'data_available','info',{'data_version':version,'rows':len(frame),
                      'mean_units':float(frame.observed_units.mean()),'p95_units':float(frame.observed_units.quantile(.95)),
                      'active_fraction':float(frame.observed_units.gt(0).mean())})
            if clock in deadlines:
                week=deadlines[clock]
                if week not in accepted:event(clock,week,'missing_data','error',{'sla_hours':rules['late_after_hours']})
            for week,group in issues.get(clock,pd.DataFrame(columns=forecasts.columns)).groupby('target_week'):
                previous=(pd.Timestamp(week)-pd.Timedelta(weeks=1)).date().isoformat()
                if previous not in accepted:
                    event(clock,week,'forecast_withheld','error',{'reason':'previous-week delivery missing/invalid at issue time'})
                    continue
                persisted[week]=group
                for row in group.to_dict('records'):
                    record={k:row[k] for k in ['product_id','target_week','prediction','lower_80','upper_80','lower_95','upper_95','model_version','data_version']}
                    record.update(issue_time=clock.isoformat(),target_end=week_close(week).isoformat(),
                                  input_delivery_version=accepted[previous]['version'],training_cutoff_exclusive=week,
                                  forecast_id=digest([stream,week,row['product_id']]),simulated=True)
                    ledger.put(stream,'forecast',f"{week}:{row['product_id']}",record);forecast_records.append(record)
                event(clock,week,'forecast_persisted','info',{'rows':len(group)})
            # Actuals are accessible here only for batches delivered after week close.
            for week,group in persisted.items():
                if week in scores or week not in accepted or clock<week_close(week):continue
                batch=accepted[week]
                matched=group.merge(batch['frame'][['product_id','observed_units']],on='product_id',how='left',validate='one_to_one')
                if matched.observed_units.isna().any():
                    event(clock,week,'scoring_incomplete','error',{'missing_forecast_products':int(matched.observed_units.isna().sum())});continue
                point=metrics(matched.observed_units,matched.prediction)
                score={'target_week':week,'scored_at':clock.isoformat(),'actual_available_at':batch['available_at'].isoformat(),
                       'actual_data_version':batch['version'],**point}
                for level in (80,95):
                    result=interval_metrics(matched.observed_units,matched[f'lower_{level}'],matched[f'upper_{level}'],level/100)
                    score[f'coverage_{level}']=result['coverage'];score[f'mean_width_{level}']=result['mean_width']
                scores[week]=score;series.append(score)
                ledger.put(stream,'score',week,score)
                event(clock,week,'error_observed_after_close','info',score)
                if point['wape'] is not None and point['wape']>rules['error_wape_investigate_above']:
                    event(clock,week,'forecast_error_signal','investigate',{'wape':point['wape']})
                recent=sorted(series,key=lambda x:x['target_week'])[-rules['coverage_window_weeks']:]
                n=sum(x['rows'] for x in recent)
                coverage=sum(x['coverage_95']*x['rows'] for x in recent)/n
                if n>=rules['minimum_scored_rows'] and coverage<rules['interval_coverage_floor_95']:
                    event(clock,week,'interval_coverage_signal','investigate',{'rolling_rows':n,'rolling_coverage_95':coverage})
        success=True
    finally:ledger.finish(success)
    pd.DataFrame(forecast_records).to_csv(output/'forecasts.csv',index=False)
    pd.DataFrame(series).to_csv(output/'scores.csv',index=False)
    (output/'events.jsonl').write_text(''.join(canonical(e)+'\n' for e in events))
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    summary={'simulation':True,'kind':kind,'stream':stream,'as_of':limit.isoformat(),
             'forecasts':len(forecast_records),'scored_weeks':len(scores),'scored_rows':sum(s['rows'] for s in series),
             'event_counts':dict(Counter(e['event'] for e in events)),
             'rules_sha256':digest(rules),'manifest_sha256':sha256(output/'manifest.json'),
             'limitation':'Delivery-time assumptions and archived forecasts; not a live deployment or a new final test.'}
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    return summary


def real_inputs(weekly,archive,freeze_path):
    p=pd.read_csv(archive,dtype={'product_id':str})
    frozen=json.loads(Path(freeze_path).read_text())
    if sha256(weekly)!=frozen['weekly_sha256']:raise ValueError('Weekly data differs from evaluated version')
    marker=json.loads(Path(archive).with_name('COMPLETED.json').read_text())
    if marker['predictions_sha256']!=sha256(archive):raise ValueError('Archived forecast file changed')
    forecasts=p.rename(columns={'issue_week':'target_week','issued_at':'issue_time','tree':'prediction',
              'lower_0.8':'lower_80','upper_0.8':'upper_80','lower_0.95':'lower_95','upper_0.95':'upper_95'})
    forecasts=forecasts[['product_id','target_week','issue_time','prediction','lower_80','upper_80','lower_95','upper_95']].copy()
    forecasts['model_version']=sha256(freeze_path)+':'+forecasts.target_week
    forecasts['data_version']=frozen['weekly_sha256']
    start=(pd.Timestamp(forecasts.target_week.min())-pd.Timedelta(weeks=1)).date().isoformat()
    frame=pd.read_csv(weekly,dtype={'product_id':str})
    frame=frame[frame.week_start.ge(start)&frame.week_start.le(forecasts.target_week.max())]
    deliveries=[{'week':w,'available_at':week_close(w).isoformat(),'frame':g[['product_id','week_start','observed_units','status']].copy()} for w,g in frame.groupby('week_start')]
    refs={'weekly_sha256':sha256(weekly),'archived_predictions_sha256':sha256(archive),'final_freeze_sha256':sha256(freeze_path)}
    return deliveries,forecasts,refs


def synthetic_inputs(scenario):
    allowed={'clean','missing_columns','dropped_products','sales_shift','late_data','invalid_quantity','activity_shift'}
    if scenario not in allowed:raise ValueError(f'Unknown synthetic scenario; choose {sorted(allowed)}')
    weeks=pd.date_range('2024-01-01',periods=8,freq='7D')
    deliveries=[];forecasts=[]
    for i,stamp in enumerate(weeks):
        week=stamp.date().isoformat()
        frame=pd.DataFrame({'product_id':[f'SYN-{j:02d}' for j in range(20)],'week_start':week,'observed_units':100.,'status':'observed'})
        arrival=week_close(week)
        if i==3:
            if scenario=='missing_columns':
                deliveries.append({'week':week,'available_at':arrival.isoformat(),'frame':frame.drop(columns='observed_units')})
                arrival+=pd.Timedelta(hours=48)
            elif scenario=='dropped_products':
                deliveries.append({'week':week,'available_at':arrival.isoformat(),'frame':frame.iloc[:10].copy()})
                arrival+=pd.Timedelta(hours=48)
            elif scenario=='invalid_quantity':
                invalid=frame.copy();invalid.loc[0,'observed_units']=-1
                deliveries.append({'week':week,'available_at':arrival.isoformat(),'frame':invalid})
                arrival+=pd.Timedelta(hours=48)
            elif scenario=='late_data':arrival+=pd.Timedelta(hours=48)
            elif scenario=='sales_shift':frame['observed_units']=300.
            elif scenario=='activity_shift':frame['observed_units']=0.
        deliveries.append({'week':week,'available_at':arrival.isoformat(),'frame':frame})
        if i:
            for product in frame.product_id:
                forecasts.append({'product_id':product,'target_week':week,
                    'issue_time':stamp.tz_localize('Europe/London').isoformat(),'prediction':100.,
                    'lower_80':90.,'upper_80':110.,'lower_95':80.,'upper_95':120.,
                    'model_version':'synthetic-fixed-100-v1','data_version':'synthetic-invented-v1'})
    return deliveries,pd.DataFrame(forecasts),{'scenario':scenario,'fixture':'entirely fictional; fixed forecast 100 and illustrative intervals; not a fitted retail model'}
