"""Local-only MLflow registration, runnable in the isolated tracking environment."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3

os.environ.setdefault('MLFLOW_ENABLE_TELEMETRY','false')


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def register(request_path, root):
    from mlflow.tracking import MlflowClient
    request_path, root = Path(request_path), Path(root).resolve()
    request = json.loads(request_path.read_text())
    for item in request['artifacts']:
        if digest(item['path']) != item['sha256']:
            raise ValueError(f'Artifact changed since tracking request: {item["path"]}')
    root.mkdir(parents=True,exist_ok=True)
    # A local lock serializes registration. Recovery finds an already-created run by its key.
    with sqlite3.connect(root/'registration.sqlite',timeout=60) as lock:
        lock.execute('CREATE TABLE IF NOT EXISTS runs (fingerprint TEXT PRIMARY KEY, run_id TEXT)')
        lock.execute('BEGIN IMMEDIATE')
        client=MlflowClient(tracking_uri='sqlite:///'+str(root/'mlflow.db'))
        fingerprint=digest(request_path)
        experiment=client.get_experiment_by_name(request['experiment'])
        eid=experiment.experiment_id if experiment else client.create_experiment(request['experiment'],artifact_location=(root/'artifacts'/request['experiment']).as_uri())
        existing=client.search_runs([eid],filter_string=f"tags.request_sha256 = '{fingerprint}'")
        run=existing[0] if existing else client.create_run(eid,tags={'request_sha256':fingerprint,
            'mlflow.runName':request['name'],'data_kind':request['data_kind'],'purpose':request['purpose']})
        run_id=run.info.run_id
        if not existing or run.info.status!='FINISHED':
            for key,value in request['params'].items():
                client.log_param(run_id,key,value if isinstance(value,(str,int,float,bool)) else json.dumps(value,sort_keys=True))
            for key,value in request['metrics'].items():
                client.log_metric(run_id,key,float(value))
            client.log_artifact(run_id,str(request_path),artifact_path='provenance')
            for index,item in enumerate(request['artifacts']):
                client.log_artifact(run_id,item['path'],artifact_path=f'files/{index:03d}')
            client.set_terminated(run_id,'FINISHED')
        lock.execute('INSERT OR REPLACE INTO runs VALUES (?,?)',(fingerprint,run_id))
    return {'run_id':run_id,'request_sha256':fingerprint,'tracking_uri':'sqlite:///'+str(root/'mlflow.db'),'reused':bool(existing)}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('request',type=Path)
    parser.add_argument('--root',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(register(args.request,args.root)))
