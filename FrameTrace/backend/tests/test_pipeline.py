import cv2
import numpy as np
from app.video import sample_frames
from app.pipeline import analyze_file


def test_analysis_smoke(tmp_path):
    path = tmp_path / 'toy.avi'
    out = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'MJPG'), 8, (320, 180))
    assert out.isOpened()
    rng = np.random.default_rng(42)
    base = rng.integers(15, 220, (180, 320, 3), dtype=np.uint8)
    for n in range(32):
        shift = np.float32([[1, 0, n], [0, 1, 0]])
        frame = cv2.warpAffine(base, shift, (320, 180))
        out.write(frame)
    out.release()
    sampled, meta = sample_frames(path)
    assert len(sampled) > 5
    result = analyze_file(path)
    assert result['classification'] == 'not_trained'
    assert set(result['detectors']) == {
        'text_consistency', 'background_motion', 'depth_consistency', 'optical_flow', 'color_consistency', 'facial_consistency'}
    assert all('status' in x for x in result['detectors'].values())
