"""Read-only HTTP checks against a running real-data application; no retraining."""
import argparse
import json
from urllib.request import urlopen

parser = argparse.ArgumentParser()
parser.add_argument('--api',default='http://127.0.0.1:8000')
parser.add_argument('--dashboard',default='http://127.0.0.1:8501')
args = parser.parse_args()
def get(path):
    with urlopen(args.api.rstrip('/')+path,timeout=60) as response:
        return json.load(response)
assert get('/health')['status']=='running'
meta=get('/meta');assert meta['coverage_end']=='2011-12-09'
assert get('/products?q=22423')['products']==['22423']
assert get('/history?product_id=22423')['history']
edge=get('/forecast?product_id=22423&mode=dataset_edge')['forecast']
assert edge['target_week']=='2011-12-05' and edge['actual'] is None
past=get('/forecast?product_id=22423&mode=historical&target_week=2011-11-28')['forecast']
assert past['actual']==236 and past['model_version'] != edge['model_version']
assert get('/forecast?product_id=22423&mode=beyond_dataset')['status']=='unavailable'
monitor=get('/monitoring');assert monitor['simulation'] and monitor['summary']['forecasts']==59395
with urlopen(args.dashboard.rstrip('/')+'/_stcore/health',timeout=10) as response:
    assert response.status==200
print('Real application HTTP smoke passed: readiness, search, history, all forecast modes, monitoring and Streamlit health.')
