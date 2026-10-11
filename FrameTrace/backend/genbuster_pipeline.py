"""Resumable, on-disk dataset pipeline for extracted real/ and fake/ video folders.

Works on 118GB+ datasets without reading video bytes during indexing or keeping
all decoded videos/features in RAM. Original video files are never modified.

Dataset name is illustrative: layout is configurable; exact original archive
contents are not assumed. Class 0 = real camera video; 1 = fully AI generated.
"""
import argparse
import csv
import hashlib
import json
import os
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path
from uuid import uuid4

from app.features import EXPORT_COLUMNS, vector_from_result
from app.pipeline import analyze_file, warm_up_models
from app.config import ENABLE_OCR, ENABLE_DEPTH, DEPTH_MODEL
from app.preprocessing import contract, profiles, VERSIONS, MOTION_ANALYZERS

VIDEO_EXTENSIONS = {'.mp4', '.mov', '.m4v', '.webm', '.avi', '.mkv'}
DB_DEFAULT = Path('data/genbuster_index.sqlite3')
SCHEMA = '''
CREATE TABLE IF NOT EXISTS videos (
  relative_path TEXT PRIMARY KEY,
  label INTEGER NOT NULL CHECK(label IN (0,1)),
  source_id TEXT NOT NULL,
  generator TEXT NOT NULL DEFAULT '',
  split TEXT NOT NULL CHECK(split IN ('train','val','test')),
  bytes INTEGER NOT NULL,
  mtime_ns INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  feature_signature TEXT,
  features TEXT,
  error TEXT,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
  index_token TEXT
);
CREATE INDEX IF NOT EXISTS idx_videos_work ON videos(status, feature_signature);
CREATE INDEX IF NOT EXISTS idx_videos_split ON videos(split, label);
CREATE TABLE IF NOT EXISTS analyzer_cache (
relative_path TEXT NOT NULL, name TEXT NOT NULL, signature TEXT NOT NULL, result TEXT NOT NULL,
PRIMARY KEY(relative_path,name,signature));
CREATE TABLE IF NOT EXISTS feature_history (relative_path TEXT, signature TEXT, features TEXT, PRIMARY KEY(relative_path,signature));
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
'''


def db_open(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=60)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA busy_timeout=60000')
    conn.executescript(SCHEMA)
    return conn


def hash_split(source_id, seed):
    """Stable assignment independent of directory enumeration order."""
    digest = hashlib.sha256(f'{seed}:{source_id}'.encode('utf8')).digest()
    percentile = int.from_bytes(digest[:8], 'big') / 2**64
    return 'train' if percentile < .8 else 'val' if percentile < .9 else 'test'


def scan_folders(root, real_dir='real', fake_dir='fake'):
    """Find videos anywhere under class-named folders; no video contents read."""
    real_dir, fake_dir = real_dir.lower(), fake_dir.lower()
    if real_dir == fake_dir:
        raise ValueError('real and fake folder names must differ')
    for base, _, names in os.walk(root):
        folder = Path(base)
        parent_parts = [p.lower() for p in folder.relative_to(root).parts]
        is_real, is_fake = real_dir in parent_parts, fake_dir in parent_parts
        if is_real == is_fake:  # ambiguous or not under either label folder
            continue
        label = 0 if is_real else 1
        for name in names:
            file = folder / name
            if file.suffix.lower() in VIDEO_EXTENSIONS:
                yield file.relative_to(root).as_posix(), label, file


def read_metadata(metadata_csv):
    if metadata_csv is None:
        return {}
    with metadata_csv.open(newline='', encoding='utf8-sig') as f:
        reader = csv.DictReader(f)
        if not {'video_path', 'source_id'} <= set(reader.fieldnames or []):
            raise ValueError('Metadata must have video_path,source_id and optionally generator,split')
        result = {}
        for row in reader:
            key = row['video_path'].replace('\\', '/').removeprefix('./')
            if not row['source_id'] or key in result:
                raise ValueError(f'Missing/duplicate source_id or path: {key}')
            result[key] = row
    return result


def index_videos(root, db, *, metadata_csv=None, real_dir='real', fake_dir='fake', seed='42'):
    root = root.resolve()
    if not root.is_dir():
        raise ValueError(f'Dataset folder not found: {root}')
    metadata = read_metadata(metadata_csv)
    count = Counter()
    conn = db_open(db)
    token = uuid4().hex
    try:
        old_root = conn.execute('SELECT value FROM settings WHERE key=?', ('dataset_root',)).fetchone()
        if old_root and Path(old_root[0]).resolve() != root:
            raise ValueError('This index database belongs to a different root. Use another --db or move the original folder back.')
        conn.execute('INSERT OR REPLACE INTO settings(key,value) VALUES (?,?)', ('dataset_root', str(root)))
        batch = []
        for relative, label, path in scan_folders(root, real_dir, fake_dir):
            record = metadata.get(relative)
            source_id = record['source_id'] if record else relative
            generator = ((record.get('generator') or '') if record else '') or (Path(relative).parts[1] if label and len(Path(relative).parts)>2 else '')
            split = ((record.get('split') or '') if record else '') or hash_split(source_id, seed)
            if split not in {'train','val','test'}:
                raise ValueError(f'Invalid split {split} for {relative}')
            stat = path.stat()
            batch.append((relative, label, source_id, generator, split, stat.st_size, stat.st_mtime_ns))
            count['fake' if label else 'real'] += 1
            if len(batch) >= 500:
                insert_batch(conn, batch, token)
                batch.clear()
        if batch:
            insert_batch(conn, batch, token)
        # Keep absent rows and feature history; do not delete extracted evidence.
        leaking = conn.execute('''SELECT source_id FROM videos GROUP BY source_id
            HAVING COUNT(DISTINCT split)>1 LIMIT 1''').fetchone()
        if leaking:
            raise ValueError(f'Source leakage across splits: {leaking[0]}')
        conn.commit()
        print('Indexed:', dict(count), 'database:', db)
        print('No videos were loaded into RAM or copied.')
        if not metadata:
            print('WARNING: splits are deterministic PER FILE, not necessarily source-group safe. '
                  'Use --metadata-csv containing shared source_id for related/derived videos.', file=sys.stderr)
    finally:
        conn.close()
    if not sum(count.values()):
        raise ValueError(f'No videos found under {real_dir}/ and {fake_dir}/ folders')
    return count


def insert_batch(conn, rows, token):
    conn.executemany('INSERT OR IGNORE INTO feature_history SELECT relative_path,feature_signature,features FROM videos WHERE relative_path=? AND features IS NOT NULL',[(row[0],) for row in rows])
    conn.executemany('''INSERT INTO videos
          (relative_path,label,source_id,generator,split,bytes,mtime_ns,index_token)
          VALUES (?,?,?,?,?,?,?,?)
          ON CONFLICT(relative_path) DO UPDATE SET
          index_token=excluded.index_token,
          label=excluded.label, source_id=excluded.source_id,
          generator=excluded.generator, split=excluded.split,
          bytes=excluded.bytes, mtime_ns=excluded.mtime_ns,
          status=CASE WHEN videos.label=excluded.label AND videos.source_id=excluded.source_id
            AND videos.split=excluded.split AND videos.bytes=excluded.bytes
            AND videos.mtime_ns=excluded.mtime_ns THEN videos.status ELSE 'pending' END,
          features=CASE WHEN videos.label=excluded.label AND videos.source_id=excluded.source_id
            AND videos.split=excluded.split AND videos.bytes=excluded.bytes
            AND videos.mtime_ns=excluded.mtime_ns THEN videos.features ELSE NULL END
    ''', [(*row, token) for row in rows])
    conn.commit()


def config_signature(sampling):
    return json.dumps(contract(sampling), sort_keys=True)


def extract(db, *, root=None, limit=None, sample_fps=None, max_frames=None,
            frame_width=None, max_duration=180, allow_disabled_models=False,
            retry_failed=False, partition=0, partitions=1, manifest=None,
            motion_fps=8.0, motion_max_frames=48, motion_width=640):
    if (not ENABLE_OCR or not ENABLE_DEPTH) and not allow_disabled_models:
        raise RuntimeError('Both OCR and depth are disabled. For all FIVE features, install models and '
                           'set ENABLE_OCR=1 ENABLE_DEPTH=1; for a speed test only, '
                           'use --allow-disabled-models (missing features are marked unavailable).')
    if not 0 <= partition < partitions:
        raise ValueError('Require 0 <= partition < partitions')
    conn = db_open(db)
    try:
        stored = conn.execute('SELECT value FROM settings WHERE key=?', ('dataset_root',)).fetchone()
        if not stored:
            raise ValueError('Index dataset first')
        root = Path(root or stored[0]).resolve()
        if not root.is_dir():
            raise ValueError(f'Missing dataset root: {root}')
        sparse = {'sample_fps': sample_fps, 'max_frames': max_frames,
                  'frame_width': frame_width, 'max_duration_seconds': max_duration}
        sparse = {key:value for key,value in sparse.items() if value is not None}
        # Optical flow and face tracking only link frames <=0.35s apart, and face needs
        # faces >=40px, so they get dense sampling instead of the sparse settings above.
        motion = {'sample_fps': float(motion_fps), 'max_frames': motion_max_frames,
                  'frame_width': motion_width, 'max_duration_seconds': max_duration}
        sampling = {name: (motion if name in MOTION_ANALYZERS else sparse) for name in VERSIONS}
        signature = config_signature(sampling)
        # Salted differently from hash_split's '42:<source_id>': with the same input, processing
        # order matched split order, so every train video was done before any val/test video.
        conn.create_function('sample_hash',1,lambda value:hashlib.sha256(('order:'+value).encode()).hexdigest())
        # Fetch the work list up front: an open read would block this connection's writes
        # whenever another partition process writes first ("database is locked").
        cursor = conn.execute('''SELECT relative_path, status, feature_signature FROM (
            SELECT relative_path, label, status, feature_signature,
                   ROW_NUMBER() OVER (PARTITION BY label ORDER BY sample_hash(relative_path)) AS class_index
            FROM videos) ORDER BY class_index, label''').fetchall()
        success, failures, skipped = 0, 0, 0
        print('Loading models...', flush=True)
        warm_up_models()
        print('Processing one video at a time; progress is saved after each video.')
        started = time.time()
        manifest_paths = None
        if manifest:
            with Path(manifest).open(encoding='utf-8-sig',newline='') as file:
                manifest_paths={row['video_path'].replace('\\','/') for row in csv.DictReader(file)}
        selected = 0
        for relpath, status, old_signature in cursor:
            if manifest_paths is not None and relpath not in manifest_paths:
                continue
            if limit is not None and selected >= limit:
                break
            selected += 1
            if partitions > 1 and int.from_bytes(hashlib.sha256(relpath.encode()).digest()[:4],'big') % partitions != partition:
                continue
            if status == 'completed' and old_signature == signature:
                skipped += 1
                continue
            if status == 'failed' and old_signature == signature and not retry_failed:
                skipped += 1
                continue
            try:
                stat = (root / relpath).stat()
                def cache(name, value):
                    settings=contract(sampling)
                    signature=json.dumps({'version':VERSIONS[name],'sampling':profiles(sampling)[name],
                        'bytes':stat.st_size,'mtime':stat.st_mtime_ns,
                        'model': {key:settings[key] for key in ('ocr','depth','depth_model','face_model','face_model_hash','face_enabled') if
                            (name=='text_consistency' and key=='ocr') or
                            (name=='depth_consistency' and key in ('depth','depth_model')) or
                            (name=='facial_consistency' and key in ('face_model','face_model_hash','face_enabled'))}},sort_keys=True)
                    if value is None:
                        row=conn.execute('SELECT result FROM analyzer_cache WHERE relative_path=? AND name=? AND signature=?',(relpath,name,signature)).fetchone()
                        return json.loads(row[0]) if row else None
                    if value['status'] not in ('error','not_available'):
                        conn.execute('INSERT OR REPLACE INTO analyzer_cache VALUES (?,?,?,?)',(relpath,name,signature,json.dumps(value)))
                        conn.commit()
                result = analyze_file(root / relpath, sampling=sampling, analyzer_cache=cache)
                feature_values = vector_from_result(result)
                feature_values['duration_seconds'] = result['video']['duration_seconds']
                # This failure mode shouldn't silently become a training example.
                if not allow_disabled_models and any(
                        result['detectors'][name]['status'] in {'not_enabled', 'not_available', 'error'}
                        for name in ('text_consistency', 'depth_consistency')):
                    raise RuntimeError('OCR or depth model was disabled/unavailable/failed: '
                                       f'{result["detectors"]["text_consistency"]["status"]}/'
                                       f'{result["detectors"]["depth_consistency"]["status"]}')
                conn.execute('INSERT OR IGNORE INTO feature_history SELECT relative_path,feature_signature,features FROM videos WHERE relative_path=? AND features IS NOT NULL',(relpath,))
                conn.execute('''UPDATE videos SET status='completed', feature_signature=?,
                    features=?, error=NULL, updated_at=CURRENT_TIMESTAMP WHERE relative_path=?''',
                    (signature, json.dumps(feature_values), relpath))
                success += 1
            except Exception as exc:
                conn.execute('''UPDATE videos SET status='failed', feature_signature=?,
                    features=NULL, error=?, updated_at=CURRENT_TIMESTAMP WHERE relative_path=?''',
                    (signature, f'{type(exc).__name__}: {exc}'[:1000], relpath))
                failures += 1
                if failures <= 10:
                    print(f'FAILED {relpath}: {exc}', file=sys.stderr)
            conn.commit()
            if (success + failures) % 20 == 0:
                print(f'Completed {success}, failed {failures}, already processed {skipped} '
                      f'elapsed {time.time()-started:.1f}s', flush=True)
            if limit is not None and selected >= limit:
                break
        print(f'Done: newly completed {success}, failed {failures}, skipped {skipped}')
    finally:
        conn.close()


def export_features(db, out, latest_config=False):
    conn = db_open(db)
    out.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    try:
        only_signature = None
        if latest_config:
            # Keep rows extracted with the most recent configuration so a partial re-extraction
            # isn't mixed with older rows (the trainer rejects mixed configurations).
            row = conn.execute('''SELECT feature_signature FROM videos WHERE status='completed'
                ORDER BY updated_at DESC LIMIT 1''').fetchone()
            only_signature = row[0] if row else None
        with out.open('w', newline='', encoding='utf8') as fh:
            writer = csv.DictWriter(fh, fieldnames=EXPORT_COLUMNS)
            writer.writeheader()
            for relative, source, gen, split, label, signature, feature_text in conn.execute('''
                   SELECT relative_path, source_id, generator, split, label, feature_signature, features
                   FROM videos WHERE status='completed' AND features IS NOT NULL
                   AND (? IS NULL OR feature_signature = ?)
                   ORDER BY relative_path''', (only_signature, only_signature)):
                vals = json.loads(feature_text)
                writer.writerow({'video_path': relative, 'source_id': source,
                    'generator': gen, 'split': split, 'label': label,
                    'feature_signature': signature, **vals})
                n += 1
    finally:
        conn.close()
    print('Exported', n, 'completed feature rows to', out)
    return n


def stats(db):
    conn = db_open(db)
    try:
        print('Indexed rows by split, label, status:')
        for row in conn.execute('SELECT split,label,status,COUNT(*) FROM videos GROUP BY split,label,status ORDER BY split,label,status'):
            print(f'  {row[0]:5s} {"fake" if row[1] else "real":5s} {row[2]:9s} {row[3]}')
        print('Bytes indexed:', conn.execute('SELECT COALESCE(SUM(bytes),0) FROM videos').fetchone()[0])
        for rel, error in conn.execute("SELECT relative_path,error FROM videos WHERE status='failed' LIMIT 5"):
            print('Failure sample:', rel, error)
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    ix = sub.add_parser('index', help='scan class-named folders; no video decoding')
    ix.add_argument('--root', type=Path, required=True)
    ix.add_argument('--db', type=Path, default=DB_DEFAULT)
    ix.add_argument('--real-dir', default='real')
    ix.add_argument('--fake-dir', default='fake')
    ix.add_argument('--seed', default='42')
    ix.add_argument('--metadata-csv', type=Path, help='optional source_id, generator, split mapping')
    ex = sub.add_parser('extract', help='resume feature extraction, one video at a time')
    ex.add_argument('--manifest',type=Path,help='CSV video_path list; reproduces an existing experiment exactly')
    ex.add_argument('--db', type=Path, default=DB_DEFAULT)
    ex.add_argument('--root', type=Path)
    ex.add_argument('--limit', type=int, help='max videos to process this run')
    ex.add_argument('--sample-fps', type=float)
    ex.add_argument('--max-frames', type=int)
    ex.add_argument('--frame-width', type=int)
    ex.add_argument('--max-duration', type=int, default=180)
    ex.add_argument('--motion-fps', type=float, default=8.0,
                    help='sampling rate for optical flow and face (they need frames <=0.35s apart)')
    ex.add_argument('--motion-max-frames', type=int, default=48)
    ex.add_argument('--motion-width', type=int, default=640,
                    help='frame width for optical flow and face (faces must be >=40px)')
    ex.add_argument('--allow-disabled-models', action='store_true')
    ex.add_argument('--retry-failed', action='store_true')
    ex.add_argument('--partition', type=int, default=0)
    ex.add_argument('--partitions', type=int, default=1)
    ep = sub.add_parser('export', help='write compact labeled features CSV')
    ep.add_argument('--db', type=Path, default=DB_DEFAULT)
    ep.add_argument('--out', type=Path, default=Path('video_features.csv'))
    ep.add_argument('--latest-config', action='store_true',
                    help='only export rows extracted with the most recent configuration')
    sp = sub.add_parser('stats', help='count videos and processing states')
    sp.add_argument('--db', type=Path, default=DB_DEFAULT)
    args = parser.parse_args()
    if args.command == 'index':
        index_videos(args.root, args.db, metadata_csv=args.metadata_csv,
                     real_dir=args.real_dir, fake_dir=args.fake_dir, seed=args.seed)
    elif args.command == 'extract':
        extract(args.db, root=args.root, limit=args.limit, sample_fps=args.sample_fps,
                max_frames=args.max_frames, frame_width=args.frame_width,
                max_duration=args.max_duration, allow_disabled_models=args.allow_disabled_models,
                motion_fps=args.motion_fps, motion_max_frames=args.motion_max_frames,
                motion_width=args.motion_width,
                retry_failed=args.retry_failed, partition=args.partition,
                partitions=args.partitions, manifest=args.manifest)
    elif args.command == 'export':
        export_features(args.db, args.out, args.latest_config)
    elif args.command == 'stats':
        stats(args.db)


if __name__ == '__main__':
    main()
