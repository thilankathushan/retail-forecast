"""Read selected products from a hash-verified compressed public demo archive."""
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]/'demo'

@lru_cache(maxsize=1)
def catalog():
    path=ROOT/'observed-sales.zip'
    manifest=json.loads((ROOT/'manifest.json').read_text())
    if hashlib.sha256(path.read_bytes()).hexdigest()!=manifest['sha256']:
        raise ValueError('Demo archive hash mismatch; restore matching release files.')
    with zipfile.ZipFile(path) as z:
        products=json.loads(z.read('products.json'))
    return {p:i for i,p in enumerate(products)}

def read(name):
    catalog()
    with zipfile.ZipFile(ROOT/'observed-sales.zip') as z:
        return json.loads(z.read(name))

def fetch(route, **params):
    ids=catalog()
    if route=='/meta':return read('meta.json')
    if route=='/monitoring':
        return read('monitoring.json') | {'simulation':True,'availability_assumption':'Assumed at local Monday close; actual delivery times are unknown.'}
    if route=='/products':
        q=str(params.get('q','')).strip().casefold();limit=int(params.get('limit',50))
        if len(q)>80 or not 1<=limit<=200:raise ValueError('Invalid search length or limit')
        matches=[p for p in ids if q in p.casefold()]
        return {'products':matches[:limit],'total':len(matches),'limit':limit}
    product=params.get('product_id')
    if product not in ids:raise ValueError('Unknown product ID')
    data=read(f'products/{ids[product]}.json')
    if route=='/history':return {'product_id':product,'history':data['history'][-int(params.get('limit',104)):]}
    if route!='/forecast':raise ValueError('Unsupported demo route')
    meta=read('meta.json');mode=params.get('mode','dataset_edge')
    if mode=='beyond_dataset':
        return {'status':'unavailable','forecast':None,'reason':f"Forecasts from {meta['beyond_week']} are withheld: the prior week is incomplete. This historical dataset cannot support a current retail forecast."}
    if mode not in ('historical','dataset_edge'):raise ValueError('Unknown forecast mode')
    week=params.get('target_week') or (meta['edge_week'] if mode=='dataset_edge' else meta['historical_weeks'][-1])
    result=data['forecasts'].get(mode+':'+week)
    return {'status':'available' if result else 'unavailable','forecast':result,'reason':None if result else 'No saved eligible forecast at this origin; four consecutive prior observed weeks are required.'}
