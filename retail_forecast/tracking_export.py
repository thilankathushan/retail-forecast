"""Export versioned result bundles to a separately installed local MLflow client."""
import json
import math
from pathlib import Path
import subprocess
from .source import sha256

PROJECT=Path(__file__).resolve().parents[1]


def flatten_numbers(value,prefix=''):
    result={}
    if isinstance(value,dict):
        for key,item in value.items():result.update(flatten_numbers(item,f'{prefix}.{key}' if prefix else key))
    elif type(value) in (int,float) and math.isfinite(value):result[prefix]=value
    return result


def log_bundle(name,kind,params,metrics,artifacts,request_path,tracking_root=None):
    request={'experiment':'retail-forecast-'+kind,'name':name,'data_kind':kind,
             'purpose':'simulated historical monitoring' if 'monitor' in name else 'versioned saved evaluation import; no refitting',
             'params':params,'metrics':flatten_numbers(metrics),
             'artifacts':[{'path':str(Path(p).resolve()),'sha256':sha256(p)} for p in artifacts]}
    request_path=Path(request_path);request_path.parent.mkdir(parents=True,exist_ok=True)
    request_path.write_text(json.dumps(request,sort_keys=True,indent=2)+'\n')
    python=PROJECT/'.venv-tracking/bin/python'
    if not python.exists():raise ValueError('Create .venv-tracking and install requirements-tracking.txt before tracking')
    result=subprocess.run([str(python),str(PROJECT/'retail_forecast/tracking.py'),str(request_path.resolve()),
                           '--root',str(tracking_root or PROJECT/'.tracking')],capture_output=True,text=True)
    if result.returncode:raise ValueError('Local MLflow logging failed: '+result.stderr[-2000:])
    response=json.loads(result.stdout.strip().splitlines()[-1])
    request_path.with_suffix('.receipt.json').write_text(json.dumps(response,indent=2)+'\n')
    return response


def track_evaluations(artifact_dir):
    artifact_dir=Path(artifact_dir)
    responses=[]
    for stage in ('development','tree','final'):
        folder=artifact_dir/stage
        report=json.loads((folder/'metrics.json').read_text())
        protocol=PROJECT/'evaluation_protocol.json'
        freeze=PROJECT/'final_freeze.json'
        params={'evaluation_stage':stage,'evaluation_config_sha256':sha256(freeze if stage=='final' else protocol),
                'weekly_data_sha256':sha256(PROJECT/'data/processed/uci/weekly.csv'),
                'training_cutoff_policy':'expanding, exclusive cutoff equals issue week; see fold/runtime artifacts',
                'last_training_cutoff_exclusive':'2011-11-28' if stage=='final' else '2011-08-29',
                'configuration':json.loads((freeze if stage=='final' else protocol).read_text())}
        if stage=='tree':params['model_configuration']=report['configurations']
        if stage=='final' and report['freeze_sha256']!=params['evaluation_config_sha256']:
            raise ValueError('Final freeze differs from recorded results')
        if stage in ('development','tree'):
            meta=report if stage=='development' else report['metadata']
            if meta['weekly_file_sha256']!=params['weekly_data_sha256'] or meta['protocol_sha256']!=sha256(protocol):
                raise ValueError('Evaluation versions differ from current data/protocol')
        artifacts=[folder/'metrics.json',folder/'predictions.csv',protocol,PROJECT/'requirements-lock.txt']
        if stage=='development':artifacts += [folder/'folds.csv',folder/'eligibility.csv']
        if stage=='tree':artifacts += [folder/'timings.csv',PROJECT/'models/uci/tree.json',PROJECT/'models/uci/tree.joblib']
        if stage=='final':artifacts += [freeze,PROJECT/'interval_calibration.json',folder/'runtime.csv',folder/'COMPLETED.json']
        responses.append(log_bundle(stage,'real',params,report,artifacts,artifact_dir/'tracking'/f'{stage}.json'))
    return responses
