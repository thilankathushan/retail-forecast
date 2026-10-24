"""Validate application export against persisted inference and frozen predictions."""
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from retail_forecast.tree import reload_model, features, predict_at
from retail_forecast.baseline import read_weekly
from retail_forecast.source import sha256

bundle_path=ROOT/'artifacts/uci/application/bundle.json'
bundle=json.loads(bundle_path.read_text())
manifest=json.loads(bundle_path.with_name('manifest.json').read_text())
assert sha256(bundle_path)==manifest['bundle_sha256']
model,meta=reload_model(ROOT/'models/uci/application/tree.joblib')
freeze=json.loads((ROOT/'final_freeze.json').read_text())
weekly=ROOT/'data/processed/uci/weekly.csv'
origin=bundle['edge_week']
frame=read_weekly(weekly,before=origin)
table=features(frame,freeze['protocol']['train_start'],origin,freeze['protocol']['min_history_weeks'])
pred=predict_at(model,table,origin).set_index('product_id')
saved=pd.DataFrame(bundle['forecasts'])
edge=saved[saved['mode'].eq('dataset_edge')].set_index('product_id')
assert set(edge.index)==set(pred.index)
np.testing.assert_allclose(edge.loc[pred.index].prediction,pred.prediction,rtol=1e-12)
assert edge.actual.isna().all()
assert (edge.training_cutoff_exclusive==origin).all()
assert origin=='2011-12-05' and bundle['beyond_week']=='2011-12-12'
historical=saved[saved['mode'].eq('historical')].sort_values(['target_week','product_id'])
final=pd.read_csv(ROOT/'artifacts/uci/final/predictions.csv',dtype={'product_id':str}).sort_values(['issue_week','product_id'])
assert len(historical)==len(final)==59395
np.testing.assert_allclose(historical.prediction,final.tree,rtol=1e-12)
np.testing.assert_allclose(historical.actual,final.actual,rtol=1e-12)
print(f'Application verified: {len(edge)} persisted/reloaded edge forecasts; {len(final)} unchanged historical rows.')
