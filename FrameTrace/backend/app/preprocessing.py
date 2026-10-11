"""Versioned per-analyzer preprocessing shared by extraction and inference."""
import os
import hashlib
from pathlib import Path
from .config import ENABLE_OCR, ENABLE_DEPTH, DEPTH_MODEL, ROOT

VERSIONS = {'text_consistency':'text-v3','background_motion':'background-v3',
            'depth_consistency':'depth-v4','optical_flow':'flow-v4',
            'color_consistency':'color-v3','facial_consistency':'face-v1'}

MOTION_ANALYZERS = ('optical_flow', 'facial_consistency')


def profiles(overrides=None):
    """Per-analyzer sampling. `overrides` is either one dict applied to every analyzer or
    a mapping of analyzer name -> dict, so motion analyzers can keep dense sampling."""
    base = {'max_duration_seconds':180}
    result = {}
    per_analyzer = bool(overrides) and set(overrides) <= set(VERSIONS)
    for name in VERSIONS:
        fps,width,cap = (8,640,1440) if name in ('optical_flow','facial_consistency') else (2,384,360)
        if name=='text_consistency':
            fps,width,cap = 2,1280,360
        prefix = name.upper()
        result[name] = dict(base,sample_fps=float(os.getenv(prefix+'_FPS',fps)),
                            frame_width=int(os.getenv(prefix+'_WIDTH',width)),max_frames=cap)
        if overrides:
            result[name].update((overrides.get(name) or {}) if per_analyzer else overrides)
    return result

def portable_path(path):
    """Path relative to the backend folder (with forward slashes) when it lives inside it,
    so a trained model's contract matches on every machine; otherwise the absolute path."""
    if not path:
        return ''
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return str(resolved)

def contract(overrides=None):
    ref=os.getenv('ANOMALY_REFERENCE_PATH','')
    ref_hash=hashlib.sha256(Path(ref).read_bytes()).hexdigest() if ref and Path(ref).is_file() else None
    face=os.getenv('FACE_MODEL_PATH','')
    face_hash=hashlib.sha256(Path(face).read_bytes()).hexdigest() if face and Path(face).is_file() else None
    return {'reference_hash':ref_hash,'face_model_hash':face_hash,'code_version':'v4','analyzers':VERSIONS,'profiles':profiles(overrides),
            'ocr':ENABLE_OCR,'depth':ENABLE_DEPTH,'depth_model':DEPTH_MODEL if ENABLE_DEPTH else None,
            'face_model':portable_path(os.getenv('FACE_MODEL_PATH','')), 'face_enabled':os.getenv('ENABLE_FACE','0')=='1'}
