import csv
import json
import numpy as np
from app.features import EXPORT_COLUMNS, FEATURES
from train_classifier import train
from app.classifier import load_model


def test_calibrated_model_and_saved_metadata(tmp_path):
    path = tmp_path / 'features.csv'
    rng = np.random.default_rng(10)
    rows = []
    for split, n in [('train', 80), ('val', 30), ('test', 30)]:
        for i in range(n):
            label = i % 2
            row = dict.fromkeys(EXPORT_COLUMNS, '')
            row.update({'video_path': f'{split}/{i}.mp4', 'source_id': f'{split}-{i}',
                        'split': split, 'label': label, 'feature_signature': ''})
            for j, key in enumerate(FEATURES):
                row[key] = (float(label) * .6 + rng.uniform(0,.2)) if key.endswith('_index') else 1
            rows.append(row)
    with path.open('w', newline='') as file:
        writer = csv.DictWriter(file, EXPORT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    output = tmp_path / 'classifier.joblib'
    report = train(path, output)
    assert output.is_file()
    assert output.with_suffix('.metrics.json').exists()
    assert report['test_auroc'] > .8
    artifact = load_model(str(output))
    assert artifact['features'] == FEATURES
