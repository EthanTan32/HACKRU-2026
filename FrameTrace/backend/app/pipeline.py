import traceback
from .video import Frame, sample_frames
from .visualizations import save_visuals
from .config import STORAGE_DIR
from .store import update_job, get_job
from .detectors import background, flow, text, depth, appearance, face
from .preprocessing import profiles, contract
import cv2
from pathlib import Path
from .detectors.common import response
from .classifier import maybe_predict, training_sampling

# Mandatory cheap C2PA verification pre-flight
try:
    import sys
    _eval_binary_dir = str(Path(__file__).resolve().parents[3] / "eval" / "binary")
    _local_binary_dir = str(Path(__file__).resolve().parents[3] / "local" / "binary")
    for _d in [_eval_binary_dir, _local_binary_dir]:
        if _d not in sys.path:
            sys.path.insert(0, _d)
    from c2pa2_checker import check_c2pa
except Exception:
    try:
        from eval.binary.c2pa2_checker import check_c2pa
    except Exception:
        check_c2pa = None

DETECTORS = [
    ('text_consistency', text.analyze),
    ('background_motion', background.analyze),
    ('depth_consistency', depth.analyze),
    ('optical_flow', flow.analyze),
    ('color_consistency', appearance.analyze),
    ('facial_consistency', face.analyze),
]


def warm_up_models():
    """Load optional models before any video is decoded.

    On Windows, initializing PaddleOCR after OpenCV has decoded frames leaves the
    process unable to touch the filesystem (WinError 6714), so every later video
    fails. Loading the models first avoids it. Failures are left for the
    detectors to report as not_available.
    """
    from .config import ENABLE_OCR, ENABLE_DEPTH
    if ENABLE_OCR:
        try:
            text.get_ocr()
        except Exception:
            pass
    if ENABLE_DEPTH:
        try:
            depth.get_depth_model()
        except Exception:
            pass


def analyze_file(path, artifact_dir=None, sampling=None, analyzer_cache=None):
    if artifact_dir is not None:
        artifact_dir = Path(artifact_dir)

    # Mandatory C2PA Pre-Flight Check:
    # Extremely cheap (~5-10ms).
    # If and only if C2PA validates 100% (code 0: valid manifest, valid signatures, no hash errors),
    # short-circuit the entire neural / heavy detector pipeline and return authentic status.
    c2pa_status = check_c2pa(str(path)) if check_c2pa is not None else 1
    if c2pa_status == 0:
        from .video import inspect_video
        metadata = inspect_video(path, max_duration_seconds=180)
        c2pa_result = {
            'c2pa_verified': True,
            'c2pa_status': 0,
            'skipped_neural': True,
            'classification': 'authentic_c2pa',
            'ai_probability': 0.0,
            'message': 'Cryptographic C2PA validation succeeded (100% valid). Neural backend bypassed.',
            'extraction_config': contract(sampling),
            'artifacts': [],
            'video': {
                'duration_seconds': round(metadata['duration'], 3),
                'fps': round(metadata['fps'], 2),
                'sampled_frames': 0,
                'analyzer_frames': {name: 0 for name, _ in DETECTORS},
            },
            'detectors': {
                name: response(name, 'not_needed', score=0.0,
                               note='Bypassed: Video cryptographically authenticated via C2PA.')
                for name, _ in DETECTORS
            },
            'timeline': [],
        }
        return c2pa_result

    # If C2PA is missing, invalid, corrupt, or anything is not 100% valid,
    # let the video through to the neural / computer vision backend!
    outputs = {}
    saved_artifacts = []
    counts = {}
    # Detectors usually share a sampling profile, so decode each profile only once
    decoded = {}

    def frames_for(profile):
        key = tuple(sorted(profile.items()))
        if key not in decoded:
            try:
                decoded[key] = sample_frames(path, **profile)
            except Exception as exc:
                decoded[key] = exc
        if isinstance(decoded[key], Exception):
            raise decoded[key]
        frames, metadata = decoded[key]
        # Fresh copies so one detector can't alter the frames another sees
        return [Frame(time=f.time, bgr=f.bgr.copy()) for f in frames], metadata

    for name, function in DETECTORS:
        try:
            cached = analyzer_cache(name, None) if analyzer_cache else None
            if cached is not None and artifact_dir is None:
                outputs[name] = cached
                continue
            frames, metadata = frames_for(profiles(sampling)[name])
            counts[name] = len(frames)
            outputs[name] = function(frames)
            outputs[name]['sampling'] = profiles(sampling)[name]
            overlay = outputs[name].pop('_overlay', None)
            if analyzer_cache:
                analyzer_cache(name, outputs[name])
            if artifact_dir is not None:
                artifact_dir.mkdir(parents=True, exist_ok=True)
                if overlay is not None and cv2.imwrite(str(artifact_dir / f'{name}_evidence.jpg'), overlay):
                    saved_artifacts.append(f'{name}_evidence')
                if name == 'color_consistency':
                    saved_artifacts.extend(save_visuals(frames, artifact_dir))
        except Exception as exc:
            outputs[name] = response(name, 'error', note=f'{type(exc).__name__}: {exc}')
    from .anomaly_calibration import apply
    for output in outputs.values():
        apply(output)
    from .video import inspect_video
    max_duration = max(p.get('max_duration_seconds', 180) for p in profiles(sampling).values())
    metadata = inspect_video(path, max_duration_seconds=max_duration)
    timeline = sorted([dict(event, detector=name)
                       for name, result in outputs.items() for event in result['events']],
                      key=lambda event: event['timestamp'])
    result = {
        'c2pa_verified': False,
        'c2pa_status': c2pa_status,
        'skipped_neural': False,
        'extraction_config': contract(sampling),
        'artifacts': saved_artifacts,
        'video': {'duration_seconds': round(metadata['duration'], 3), 'fps': round(metadata['fps'], 2),
                  'sampled_frames': max(counts.values(), default=0), 'analyzer_frames': counts},
        'detectors': outputs, 'timeline': timeline,
    }
    result.update(maybe_predict(result))
    return result


def analyze_job(job_id):
    job = get_job(job_id)
    if job is None:
        return
    try:
        update_job(job_id, status='running')
        result = analyze_file(job['path'], STORAGE_DIR / 'artifacts' / job_id, sampling=training_sampling())
        update_job(job_id, status='completed', result=result)
    except Exception as exc:
        traceback.print_exc()
        update_job(job_id, status='failed', error=f'{type(exc).__name__}: {exc}')
