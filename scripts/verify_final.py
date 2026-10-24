"""Reconcile saved final predictions without fitting or re-evaluating models."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from retail_forecast.evaluation import metrics
from retail_forecast.intervals import interval_metrics,bounds
from retail_forecast.source import sha256
r=Path('artifacts/uci/final')
report=json.loads((r/'metrics.json').read_text())
frozen=json.loads(Path('final_freeze.json').read_text())
cal=json.loads(Path('interval_calibration.json').read_text())
pred=pd.read_csv(r/'predictions.csv',dtype={'product_id':str})
audit=pd.read_csv(r/'eligibility.csv',dtype={'product_id':str})
scored=pred[pred.scored]
assert sha256('final_freeze.json')==report['freeze_sha256']
assert cal['end_exclusive']==frozen['protocol']['holdout_start']
assert not cal['uses_holdout_outcomes']
assert pred.issue_week.ge(frozen['protocol']['holdout_start']).all()
assert pred.issue_week.lt(frozen['protocol']['holdout_end_exclusive']).all()
assert pred.issue_week.nunique()==13
assert not pred.duplicated(['issue_week','product_id']).any()
assert set(zip(scored.issue_week,scored.product_id))==set(zip(audit[audit.scored].issue_week,audit[audit.scored].product_id))
for model in report['point']:
 for k,v in metrics(scored.actual,scored[model]).items():assert np.isclose(v,report['point'][model][k])
for level in frozen['levels']:
 lo,hi=bounds(pred.tree,pred.scale,cal['levels'][str(level)]['quantile'])
 np.testing.assert_allclose(lo,pred[f'lower_{level}'])
 np.testing.assert_allclose(hi,pred[f'upper_{level}'])
 for k,v in interval_metrics(scored.actual,scored[f'lower_{level}'],scored[f'upper_{level}'],level).items():
  assert np.isclose(v,report['intervals'][str(level)][k])
assert frozen['frozen_at_utc'] < json.loads((r/'STARTED.json').read_text())['started_at_utc']
print('Frozen-before-start provenance, common cohort, pooled metrics and fixed historical intervals verified.')
