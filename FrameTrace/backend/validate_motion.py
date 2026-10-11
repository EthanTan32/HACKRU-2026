"""Independent motion-only validation; explicitly not a six-analyzer evaluation."""
import argparse
import csv
import json
from pathlib import Path
import numpy as np
from sklearn.metrics import roc_auc_score
from app.video import sample_frames
from app.detectors.flow import analyze

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--root',type=Path,required=True)
p.add_argument('--exclude',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--count',type=int,default=40)
a=p.parse_args()
excluded={r['video_path'] for r in csv.DictReader(a.exclude.open(encoding='utf-8-sig'))}
rng=np.random.default_rng(20261010)
selected=[]
for label,folder in enumerate(('real','fake')):
    reservoir=[]
    seen=0
    for path in sorted((a.root/folder).rglob('*.mp4')):
        relative=path.relative_to(a.root).as_posix()
        if relative in excluded:
            continue
        seen+=1
        if len(reservoir)<a.count//2:
            reservoir.append(path)
        else:
            j=int(rng.integers(seen))
            if j<len(reservoir):
                reservoir[j]=path
    selected.extend((label,path) for path in reservoir)
rows=[]
for label,path in selected:
    try:
        frames,_=sample_frames(path,sample_fps=8,max_frames=240,frame_width=384,max_duration_seconds=180)
        result=analyze(frames)
        rows.append({'path':path.relative_to(a.root).as_posix(),'label':label,'status':result['status'],'metrics':result['metrics']})
        print(len(rows),label,result['status'],flush=True)
    except Exception as exc:
        rows.append({'path':str(path),'label':label,'status':'error','error':str(exc)})
valid=[r for r in rows if r['status']=='ok']
report={'seed':20261010,'excluded_original_csv':str(a.exclude),'configuration':{'fps':8,'width':384,'max_frames':240},
        'rows':rows,'usable_count':len(valid),'total_count':len(rows),
        'limitation':'Motion-only exploratory evaluation. No learned classifier, no source-group metadata; no full-system generalization claim.'}
if len({r['label'] for r in valid})==2:
    report['raw_local_deformation_auroc']=float(roc_auc_score([r['label'] for r in valid],[r['metrics']['median_local_deformation'] for r in valid]))
    report['raw_acceleration_auroc']=float(roc_auc_score([r['label'] for r in valid],[r['metrics']['median_p90_relative_velocity_change'] for r in valid]))
a.output.parent.mkdir(parents=True,exist_ok=True)
a.output.write_text(json.dumps(report,indent=2),encoding='utf8')
print({k:v for k,v in report.items() if k!='rows'})
