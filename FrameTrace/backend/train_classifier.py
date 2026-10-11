"""Train and validate a five-analyzer feature classifier on real/fake labels.

Train on train, calibrate probabilities on independent val, report unseen test.
Does not fit or fine-tune any underlying OCR, depth, or optical-flow model.
Input must use group-safe splits, ideally with entire unseen generators in test.
"""
import argparse
import json
from pathlib import Path
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier
from sklearn.metrics import accuracy_score, balanced_accuracy_score, precision_score, recall_score
from sklearn.frozen import FrozenEstimator
from sklearn.impute import SimpleImputer
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score, brier_score_loss
from sklearn.pipeline import Pipeline

from app.features import FEATURES


def evaluate(y, probabilities):
    predictions = (probabilities >= .5).astype(int)
    tn,fp,fn,tp = confusion_matrix(y,predictions,labels=[0,1]).ravel()
    return {'accuracy':float(accuracy_score(y,predictions)),
            'balanced_accuracy':float(balanced_accuracy_score(y,predictions)),
            'precision':float(precision_score(y,predictions,zero_division=0)),
            'recall':float(recall_score(y,predictions,zero_division=0)),
            'auroc':float(roc_auc_score(y,probabilities)),
            'false_positive_rate':float(fp/max(tn+fp,1)),
            'confusion_matrix':[[int(tn),int(fp)],[int(fn),int(tp)]]}


def train(csv_path, output, held_out_generator=None):
    df = pd.read_csv(csv_path)
    if output.exists():
        raise ValueError('Output already exists; choose a new model path to preserve it')
    if held_out_generator:
        groups = set(df.loc[df['generator']==held_out_generator,'source_id'])
        # Test exclusively on held-out generator plus real test groups.
        familiar_fake=(df['label']==1)&~df['source_id'].isin(groups)&(df['split']=='test')
        familiar_groups=set(df.loc[familiar_fake,'source_id'])
        df.loc[df['source_id'].isin(familiar_groups),'split']='train'
        df.loc[df['source_id'].isin(groups),'split']='test'
        if not groups:
            raise ValueError('Held-out generator not found')
    required = set(FEATURES) | {'label','split','source_id'}
    if missing := required - set(df.columns):
        raise ValueError('Missing columns: ' + ', '.join(sorted(missing)))
    for column in FEATURES:
        df[column] = pd.to_numeric(df[column], errors='coerce')
    df['label'] = pd.to_numeric(df['label'], errors='raise')
    if not set(df['label'].unique()) <= {0, 1}:
        raise ValueError('Use real=0, fake=1 only')
    splits = {'train', 'val', 'test'}
    if not splits <= set(df['split'].unique()):
        raise ValueError('Need separate train, val, test splits for honest calibration and evaluation')
    grouped = df.groupby('source_id')['split'].nunique()
    if (grouped > 1).any():
        raise ValueError('Source-group data leakage: related files occur in different splits')
    if 'feature_signature' in df and df['feature_signature'].dropna().nunique() > 1:
        raise ValueError('Mixed extraction configurations; rerun extraction with one configuration')
    train_data, val_data, test_data = (df.loc[df['split'] == name] for name in ('train','val','test'))
    for name, part in zip(('train','val','test'), (train_data,val_data,test_data)):
        if part['label'].nunique() != 2:
            raise ValueError(f'{name} must contain both real and fake labeled videos')
    if df['source_id'].isna().any():
        raise ValueError('Missing source IDs cannot establish group-safe splits')
    X_tr, y_tr = train_data[FEATURES], train_data['label']
    # NaNs retained by the imputer and missing-availability columns are explicit.
    candidates = {
        'logistic': LogisticRegression(max_iter=1500, class_weight='balanced', random_state=42),
        'random_forest': RandomForestClassifier(n_estimators=150,min_samples_leaf=3,class_weight='balanced',random_state=42,n_jobs=-1),
        'xgboost': XGBClassifier(n_estimators=150,max_depth=3,learning_rate=.05,subsample=.8,colsample_bytree=.8,random_state=42,n_jobs=2),
    }
    baselines = {}
    fitted = {}
    for name, estimator in candidates.items():
        base = Pipeline([('impute',SimpleImputer(strategy='median',keep_empty_features=True,add_indicator=True)),
                         ('scale',StandardScaler()),('model',estimator)])
        base.fit(X_tr,y_tr)
        calibrated = CalibratedClassifierCV(FrozenEstimator(base),method='sigmoid')
        calibrated.fit(val_data[FEATURES],val_data['label'])
        fitted[name]=calibrated
        baselines[name] = evaluate(test_data['label'],calibrated.predict_proba(test_data[FEATURES])[:,1])
    # Selection is fixed to XGBoost; test results never select a winning model.
    calibrated = fitted['xgboost']
    ablations = {}
    from app.features import DETECTOR_NAMES, RAW_METRICS
    for detector, prefix in DETECTOR_NAMES.items():
        removed = {f'{prefix}_{suffix}' for suffix in ('anomaly_index','available','insufficient','unavailable')} | {key for key,(owner,_) in RAW_METRICS.items() if owner==detector}
        columns = [key for key in FEATURES if key not in removed]
        base = Pipeline([('impute',SimpleImputer(strategy='median',keep_empty_features=True,add_indicator=True)),
                         ('model',XGBClassifier(n_estimators=150,max_depth=3,learning_rate=.05,subsample=.8,colsample_bytree=.8,random_state=42,n_jobs=2))])
        base.fit(train_data[columns],y_tr)
        model = CalibratedClassifierCV(FrozenEstimator(base),method='sigmoid')
        model.fit(val_data[columns],val_data['label'])
        ablations[detector] = evaluate(test_data['label'],model.predict_proba(test_data[columns])[:,1])
    pred_prob = calibrated.predict_proba(test_data[FEATURES])[:, 1]
    predictions = (pred_prob >= .5).astype(int)
    report = {
        'baselines': baselines, 'ablations_without_analyzer': ablations,
        'held_out_generator':held_out_generator,
        'test_count': int(len(test_data)),
        'test_auroc': float(roc_auc_score(test_data['label'], pred_prob)),
        'test_brier_score': float(brier_score_loss(test_data['label'], pred_prob)),
        'test_confusion_matrix_real_fake': confusion_matrix(test_data['label'], predictions).tolist(),
        'test_classification': classification_report(test_data['label'], predictions,
                                                      output_dict=True, zero_division=0),
        'samples': {name: len(part) for name, part in zip(('train','val','test'),
                           (train_data,val_data,test_data))},
    }
    # Try to retain extraction sampling/config metadata for safety checks at inference time.
    config = None
    if 'feature_signature' in df:
        signatures = df['feature_signature'].dropna().unique().tolist()
        if len(signatures) == 1:
            config = json.loads(signatures[0])
    artifact = {
        'model': calibrated, 'features': list(FEATURES), 'extraction_config': config,
        'labels': {'real':0,'fake':1}, 'trained_utc': datetime.now(timezone.utc).isoformat(),
        'evaluation': report, 'note': ('Probability calibrated on held-out validation data; '
                                     'performance on unseen generators is not guaranteed.'),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, output)
    (output.with_suffix('.metrics.json')).write_text(json.dumps(report, indent=2), encoding='utf8')
    print(json.dumps(report, indent=2))
    print('Saved classifier:', output)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv', type=Path)
    parser.add_argument('--output', type=Path, default=Path('data/classifier.joblib'))
    parser.add_argument('--held-out-generator')
    args = parser.parse_args()
    train(args.csv, args.output, args.held_out_generator)


if __name__ == '__main__':
    main()
