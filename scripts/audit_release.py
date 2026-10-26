"""Bounded release-file hygiene check; never prints suspected secret values."""
import json
from pathlib import Path
import re
import subprocess

root=Path(__file__).resolve().parents[1]
paths=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z','--','.'],cwd=root).decode().split('\0')
paths=sorted({p for p in paths if p})
findings=[]; sizes=[]
patterns=[r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
          r'\bAKIA[0-9A-Z]{16}\b',r'\bgh[pousr]_[A-Za-z0-9]{30,}\b',
          r'\bsk-[A-Za-z0-9_-]{30,}\b',r'(?i)(?:password|api_key|secret_key)\s*=\s*[\x22\x27][^\x22\x27\s]{12,}[\x22\x27]']
for rel in paths:
    path=root/rel
    if path.is_symlink(): findings.append({'path':rel,'reason':'symlink requires review'});continue
    if not path.is_file(): continue
    size=path.stat().st_size;sizes.append({'path':rel,'bytes':size})
    if size>5*1024*1024 and rel != 'demo/observed-sales.zip':findings.append({'path':rel,'reason':'larger than 5 MiB'})
    if rel.startswith(('data/raw/','data/processed/','models/','artifacts/','.venv/','.venv-app/','.venv-tracking/','.tracking/')) or path.suffix in {'.joblib','.pkl','.xlsx','.sqlite'}:
        findings.append({'path':rel,'reason':'private/generated/binary path in release candidate'})
    if path.name=='.env' or (path.name.startswith('.env.') and path.name!='.env.example'):
        findings.append({'path':rel,'reason':'environment secrets file'})
    if size<=5*1024*1024 and path.suffix.lower() not in {'.png','.jpg','.jpeg'}:
        try: text=path.read_text()
        except UnicodeError: continue
        if any(re.search(pattern,text) for pattern in patterns):
            findings.append({'path':rel,'reason':'possible secret pattern; inspect locally'})
report={'scope':'Git-tracked and unignored candidate files in Project 3 only; ignored runtime files excluded',
        'candidate_files':len(sizes),'candidate_bytes':sum(p['bytes'] for p in sizes),
        'largest_files':sorted(sizes,key=lambda p:p['bytes'],reverse=True)[:10],
        'findings':findings,'limitations':'Pattern scan is not a proof of absence of secrets; PNGs visually inspected separately. Git history and vulnerability scanning are not covered.',
        'permitted_demo_asset':'demo/observed-sales.zip: attributed derived product aggregates, hash-verified by cloud tests; explicit size exception',
        'code_license':'MIT for original code; UCI dataset remains CC BY 4.0 with separate attribution'}
out=root/'reports/release';out.mkdir(parents=True,exist_ok=True)
(out/'audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
raise SystemExit(bool(findings))
