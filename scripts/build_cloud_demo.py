"""Export compact, indexed public aggregates; no raw/customer data or models."""
import hashlib
import json
from pathlib import Path
import zipfile
root=Path(__file__).resolve().parents[1]
source=root/'artifacts/uci/application/bundle.json'
b=json.loads(source.read_text())
m=json.loads(source.with_name('manifest.json').read_text())
assert hashlib.sha256(source.read_bytes()).hexdigest()==m['bundle_sha256']
products={p:{'history':h,'forecasts':{}} for p,h in b['history'].items()}
for f in b['forecasts']:
    products[f['product_id']]['forecasts'][f['mode']+':'+f['target_week']]=f
meta={k:v for k,v in b.items() if k not in ('history','forecasts','monitoring')}
meta.update(product_count=len(products),historical_weeks=sorted({f['target_week'] for f in b['forecasts'] if f['mode']=='historical'}))
out=root/'demo';out.mkdir(exist_ok=True)
with zipfile.ZipFile(out/'observed-sales.zip','w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    def put(name,value):z.writestr(name,json.dumps(value,separators=(',',':'),allow_nan=False))
    put('meta.json',meta);put('products.json',sorted(products));put('monitoring.json',b['monitoring'])
    for i,(p,value) in enumerate(sorted(products.items())):put(f'products/{i}.json',value)
(out/'manifest.json').write_text(json.dumps({'sha256':hashlib.sha256((out/'observed-sales.zip').read_bytes()).hexdigest(),'source_bundle_sha256':m['bundle_sha256'],'products':len(products),'purpose':'Public derived product-week observations and saved historical forecasts; not raw transactions'},indent=2)+'\n')
print((out/'observed-sales.zip').stat().st_size)
