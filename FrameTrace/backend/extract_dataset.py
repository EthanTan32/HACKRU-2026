"""Legacy labeled-CSV feature extractor for small/custom video datasets.

For large datasets with real/ and fake/ folders, prefer genbuster_pipeline.py:
it keeps a resumable SQLite index and avoids redoing completed videos.
Input CSV: video_path,label,split,source_id; optional generator.
"""
import argparse
import csv
import json
from pathlib import Path

from app.features import EXPORT_COLUMNS, vector_from_result
from app.pipeline import analyze_file


def extract_row(item, root):
    location = Path(item['video_path'])
    path = location if location.is_absolute() else root / location
    result = analyze_file(path)
    return {
        'video_path': item['video_path'], 'source_id': item['source_id'],
        'generator': item.get('generator', ''), 'split': item['split'],
        'label': item['label'], 'feature_signature': json.dumps(result['extraction_config'], sort_keys=True),
        'duration_seconds': result['video']['duration_seconds'],
        **vector_from_result(result),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('labels_csv', type=Path)
    parser.add_argument('--out', type=Path, default=Path('video_features.csv'))
    args = parser.parse_args()
    with args.labels_csv.open(newline='', encoding='utf8') as fh:
        reader = csv.DictReader(fh)
        if not {'video_path', 'label', 'split', 'source_id'} <= set(reader.fieldnames or []):
            raise ValueError('CSV requires video_path,label,split,source_id')
        with args.out.open('w', newline='', encoding='utf8') as out:
            writer = csv.DictWriter(out, fieldnames=EXPORT_COLUMNS)
            writer.writeheader()
            seen = {}
            for row in reader:
                if row['label'] not in ('0','1') or row['split'] not in ('train','val','test'):
                    raise ValueError('label must be 0/1 and split must be train/val/test')
                source, split = row['source_id'], row['split']
                if source in seen and seen[source] != split:
                    raise ValueError(f'Source leakage: {source} appears in multiple splits')
                seen[source] = split
                writer.writerow(extract_row(row, args.labels_csv.parent))
                out.flush()
    print('Saved features:', args.out)


if __name__ == '__main__':
    main()
