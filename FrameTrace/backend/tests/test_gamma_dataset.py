from pathlib import Path
import csv
import json

import cv2
import numpy as np

from app.detectors.appearance import aligned_appearance_error, analyze
from app.video import Frame
from genbuster_pipeline import index_videos, extract, export_features, db_open, hash_split


def make_video(path, seed):
    path.parent.mkdir(parents=True, exist_ok=True)
    out = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'MJPG'), 8, (160, 96))
    assert out.isOpened()
    rng = np.random.default_rng(seed)
    base = rng.integers(15, 235, (96, 160, 3), dtype=np.uint8)
    for i in range(24):
        moved = cv2.warpAffine(base, np.float32([[1, 0, i // 3], [0, 1, 0]]), (160, 96))
        if seed == 2 and i > 12:
            moved[20:55, 30:70, 1] = np.clip(moved[20:55, 30:70, 1].astype(int) + 70, 0, 255)
        out.write(moved)
    out.release()


def test_gamma_detection_zero_for_identical_frame():
    rng = np.random.default_rng(3)
    f = rng.integers(20, 240, (120, 170, 3), dtype=np.uint8)
    metrics = aligned_appearance_error(f, f)
    assert metrics is not None
    assert metrics['shadow_gamma_p85'] < .01
    assert metrics['highlight_gamma_p85'] < .01
    assert metrics['saturation_p85'] < .01


def test_full_folder_index_extract_resume_export(tmp_path):
    root = tmp_path / 'GenBuster-200K'
    make_video(root / 'real' / 'camera' / 'r1.avi', 1)
    make_video(root / 'fake' / 'generator1' / 'f1.avi', 2)
    db = tmp_path / 'features.sqlite3'
    counts = index_videos(root, db)
    assert counts['real'] == 1 and counts['fake'] == 1
    extract(db, root=root, limit=2, sample_fps=2, max_frames=8,
            frame_width=160, max_duration=30, allow_disabled_models=True)
    with db_open(db) as conn:
        rows = conn.execute('SELECT label,status,features FROM videos ORDER BY label').fetchall()
    assert [(r[0],r[1]) for r in rows] == [(0,'completed'), (1,'completed')]
    for _, _, raw in rows:
        features = json.loads(raw)
        assert 'color_anomaly_index' in features
        assert 'color_available' in features
        assert features['text_available'] == 0
    # Re-running the same configuration preserves results and skips decoding.
    extract(db, root=root, limit=2, sample_fps=2, max_frames=8,
            frame_width=160, max_duration=30, allow_disabled_models=True)
    destination = tmp_path / 'features.csv'
    assert export_features(db, destination) == 2
    with destination.open(newline='') as f:
        exported = list(csv.DictReader(f))
    assert {int(r['label']) for r in exported} == {0, 1}
    assert all(r['feature_signature'] for r in exported)
    assert all(r['color_available'] for r in exported)


def test_source_hash_split_is_deterministic():
    assert hash_split('same-source', '42') == hash_split('same-source', '42')
