"""Fit anomaly reference from cached real validation results, never test clips."""
import argparse
import json
import sqlite3
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--db',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
if a.output.exists():
    raise ValueError('Choose a new output path; existing calibration is preserved')
reference={'version':'v4'}
reference_profiles = {}
with sqlite3.connect(a.db) as db:
    # Only use videos extracted with the newest configuration, so older extractions with
    # different sampling (e.g. before dense motion sampling) aren't mixed in.
    latest = db.execute("SELECT feature_signature FROM videos WHERE status='completed' ORDER BY updated_at DESC LIMIT 1").fetchone()
    latest = latest[0] if latest else None
    for name in ('optical_flow','facial_consistency'):
        values=[]
        seen = set()
        for relative, raw, signature, current in db.execute('SELECT c.relative_path,c.result,c.signature,v.feature_signature FROM analyzer_cache c JOIN videos v ON v.relative_path=c.relative_path WHERE v.label=0 AND v.split=? AND c.name=? AND v.status=? AND v.feature_signature=? ORDER BY c.rowid DESC',('val',name,'completed',latest)):
            cached = json.loads(signature)
            active = json.loads(current)
            if cached['sampling'] != active.get('profiles',{}).get(name) or cached['version'] != active.get('analyzers',{}).get(name):
                continue
            if relative in seen:
                continue
            profile = cached['sampling']
            if name in reference_profiles and reference_profiles[name] != profile:
                raise ValueError('Mixed sampling profiles; use a single experiment configuration')
            reference_profiles[name] = profile
            seen.add(relative)
            result=json.loads(raw)
            values.extend(s['raw_value'] for s in result.get('segments',[]) if s['confidence']>=.5)
        reference[name]=values
        print(name,len(values),'reference segments')
reference['profiles'] = reference_profiles
a.output.parent.mkdir(parents=True,exist_ok=True)
a.output.write_text(json.dumps(reference),encoding='utf8')
