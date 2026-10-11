from fastapi.testclient import TestClient
import cv2
import numpy as np

import app.main as main_module
import app.store as store_module
import app.pipeline as pipeline_module


def test_upload_analyze_fetch_delete(tmp_path, monkeypatch):
    monkeypatch.setattr(main_module, 'UPLOAD_DIR', tmp_path / 'uploads')
    monkeypatch.setattr(main_module, 'STORAGE_DIR', tmp_path)
    monkeypatch.setattr(store_module, 'STORAGE_DIR', tmp_path)
    monkeypatch.setattr(store_module, 'DB_PATH', tmp_path / 'jobs.sqlite3')
    monkeypatch.setattr(pipeline_module, 'STORAGE_DIR', tmp_path)
    path = tmp_path / 'input.avi'
    video = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'MJPG'), 8, (192, 128))
    assert video.isOpened()
    rng = np.random.default_rng(5)
    base = rng.integers(30, 220, (128, 192, 3), dtype=np.uint8)
    for i in range(32):
        video.write(cv2.warpAffine(base, np.float32([[1, 0, i], [0, 1, 0]]), (192, 128)))
    video.release()

    with TestClient(main_module.app) as client:
        assert client.get('/api/health').status_code == 200
        with path.open('rb') as fh:
            uploaded = client.post('/api/videos', files={'video': ('input.avi', fh, 'video/x-msvideo')})
        assert uploaded.status_code == 202, uploaded.text
        job_id = uploaded.json()['video_id']
        status = client.get(f'/api/videos/{job_id}/status')
        assert status.json()['status'] == 'completed', status.text
        results = client.get(f'/api/videos/{job_id}/results')
        assert results.status_code == 200, results.text
        assert results.json()['classification'] == 'not_trained'
        assert 'optical_flow' in results.json()['detectors']
        assert 'color_consistency' in results.json()['detectors']
        assert 'gamma_shadows' in results.json()['artifacts']
        assert 'saturation_boost' in results.json()['artifacts']
        image = client.get(f'/api/videos/{job_id}/artifacts/optical_flow')
        assert image.status_code == 200
        assert image.headers['content-type'] == 'image/jpeg'
        assert client.get(f'/api/videos/{job_id}/artifacts/gamma_shadows').status_code == 200
        assert client.get(f'/api/videos/{job_id}/artifacts/saturation_boost').status_code == 200
        assert client.delete(f'/api/videos/{job_id}').status_code == 204
        assert client.get(f'/api/videos/{job_id}/results').status_code == 404
