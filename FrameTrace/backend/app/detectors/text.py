from functools import lru_cache
import cv2
import numpy as np
from .common import response
from ..config import ENABLE_OCR


def levenshtein(a: str, b: str) -> int:
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        row = [i]
        for j, cb in enumerate(b, 1):
            row.append(min(previous[j] + 1, row[j-1] + 1, previous[j-1] + (ca != cb)))
        previous = row
    return previous[-1]


@lru_cache(maxsize=1)
def get_ocr():
    # With paddlepaddle-gpu on Windows, PyTorch's CUDA DLLs must load before Paddle's;
    # the reverse order makes `import torch` fail (WinError 127) for the depth model.
    try:
        import torch  # noqa: F401
    except ImportError:
        pass
    from paddleocr import PaddleOCR
    return PaddleOCR(use_doc_orientation_classify=False, use_doc_unwarping=False,
                     use_textline_orientation=False)


def recognize(frame):
    return recognize_many([frame])[0]


def recognize_many(frames):
    """OCR several frames in one call; PaddleOCR returns one result per input, in order."""
    results = list(get_ocr().predict(list(frames)))
    if len(results) != len(frames):
        raise RuntimeError(f'OCR returned {len(results)} results for {len(frames)} frames')
    return [_detections(result) for result in results]


def _detections(result):
    out = []
    # PaddleOCR 3.x result objects support item lookup; JSON result wraps under `res`.
    data = result.json if hasattr(result, 'json') else result
    if callable(data):
        data = data()
    if 'res' in data:
        data = data['res']
    for txt, confidence, box in zip(data.get('rec_texts', []),
                                     data.get('rec_scores', []),
                                     data.get('rec_boxes', [])):
        normalized = ''.join(c for c in txt.upper() if c.isalnum())
        if len(normalized) < 3 or float(confidence) < .85:
            continue
        x1, y1, x2, y2 = map(float, box)
        out.append({'text': normalized, 'score': float(confidence),
                    'center': ((x1+x2)/2, (y1+y2)/2),
                    'size': max(1, (x2-x1)*(y2-y1))})
    return out


def analyze(frames):
    if not ENABLE_OCR:
        return response('text_consistency', 'not_enabled',
                        note='Set ENABLE_OCR=1 and install backend/requirements-models.txt')
    try:
        get_ocr()
    except Exception as exc:
        return response('text_consistency', 'not_available', note=f'OCR model failed to initialize: {exc}')
    tracks, next_id = [], 0
    h, w = frames[0].bgr.shape[:2]
    indices = list(range(0, len(frames), 2))
    try:
        all_detections = recognize_many([frames[idx].bgr for idx in indices])
    except Exception as exc:
        return response('text_consistency', 'error', note=f'OCR inference error: {exc}')
    for idx, detections in zip(indices, all_detections):
        f = frames[idx]
        taken = set()
        for det in detections:
            choice, best = None, float('inf')
            for tr in tracks:
                if tr['id'] in taken or idx - tr['last_idx'] > 6:
                    continue
                distance = np.linalg.norm(np.array(det['center'])-np.array(tr['center']))
                area_ratio = det['size']/tr['size']
                if distance < .13 * max(w,h) and .35 < area_ratio < 2.85 and distance < best:
                    choice, best = tr, distance
            if choice is None:
                choice = {'id': next_id, 'history': [], 'center': det['center'],
                          'size': det['size'], 'last_idx': idx}
                tracks.append(choice)
                next_id += 1
            choice['history'].append((f.time, det['text'], det['score']))
            choice['center'], choice['size'], choice['last_idx'] = det['center'], det['size'], idx
            taken.add(choice['id'])
    events, changes, usable = [], [], 0
    for tr in tracks:
        hist = tr['history']
        if len(hist) < 4:
            continue
        usable += 1
        # Require two different readings, each stable for >=2 adjacent OCR samples.
        runs = []
        for stamp, word, conf in hist:
            if runs and runs[-1]['word'] == word:
                runs[-1]['count'] += 1
            else:
                runs.append({'word': word, 'count': 1, 'time': stamp})
        stable = [r for r in runs if r['count'] >= 2]
        for left, right in zip(stable, stable[1:]):
            if left['word'] == right['word']:
                continue
            delta = levenshtein(left['word'], right['word']) / max(len(left['word']), len(right['word']))
            changes.append(delta)
            events.append({'timestamp': right['time'], 'type': 'stable_text_change',
                           'severity': round(delta, 3),
                           'detail': f'{left["word"]} → {right["word"]} (tracked region {tr["id"]})'})
    if not usable:
        return response('text_consistency', 'insufficient_data',
                        metrics={'text_regions_seen': len(tracks)},
                        note='No text tracked reliably for four OCR observations')
    return response('text_consistency', 'ok', min(1, sum(changes)/max(usable, 1)), events,
                    {'stable_text_tracks': usable, 'confirmed_changes': len(changes)},
                    'Tracks by image-space proximity; improvements should use camera-compensated tracking.')
