"""Installed dependency license metadata; not a legal clearance or vulnerability scan."""
import importlib.metadata as metadata
import json
from pathlib import Path
import sys
rows=[]
for dist in metadata.distributions():
    if dist.metadata['Name']=='retail-forecast':continue
    license_text=dist.metadata.get('License-Expression') or dist.metadata.get('License') or 'See package LICENSE; metadata unspecified'
    rows.append({'name':dist.metadata['Name'],'version':dist.version,'license_metadata':license_text[:500]})
path=Path(sys.argv[1]);path.parent.mkdir(parents=True,exist_ok=True)
path.write_text(json.dumps(sorted(rows,key=lambda r:r['name'].lower()),indent=2)+'\n')
print(f'Wrote {len(rows)} installed dependency records to {path}')
