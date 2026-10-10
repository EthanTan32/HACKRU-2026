"""Empirical reference distributions fitted exclusively on real validation clips."""
import json
import os
from pathlib import Path
import numpy as np

def apply(result):
    path = os.getenv('ANOMALY_REFERENCE_PATH','')
    if not path or not Path(path).is_file() or not result.get('segments'):
        return
    try:
        payload=json.loads(Path(path).read_text(encoding='utf8'))
    except (ValueError,OSError):
        result['note'] += ' Reference calibration could not be read; raw measurements remain available.'
        return
    if payload.get('version')!='v4':
        return
    expected = payload.get('profiles',{}).get(result['name'])
    if expected is not None and expected != result.get('sampling'):
        result['note'] += ' Reference sampling differs; only raw measurements are shown.'
        return
    reference=np.asarray(payload.get(result['name'],[]),float)
    if len(reference)<30:
        return
    events=[]
    for segment in result['segments']:
        value=segment['raw_value']
        index=float((np.sum(reference<=value)+.5)/(len(reference)+1))
        segment['anomaly_index']=index
        if value>np.quantile(reference,.99) and segment['confidence']>=.5:
            events.append({'timestamp':segment['timestamp'],'type':'calibrated_temporal_residual',
                           'severity':index,'detail':f'Raw residual {value:.4g} exceeds real validation reference; this is not P(AI).'})
    result['anomaly_index']=float(np.median([s['anomaly_index'] for s in result['segments']]))
    result['events']=events
