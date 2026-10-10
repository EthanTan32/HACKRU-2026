"""Versioned per-analyzer preprocessing shared by extraction and inference."""
import os
import hashlib
from pathlib import Path
from .config import ENABLE_OCR, ENABLE_DEPTH, DEPTH_MODEL

VERSIONS = {'text_consistency':'text-v3','background_motion':'background-v3',
            'depth_consistency':'depth-v4','optical_flow':'flow-v4',
            'color_consistency':'color-v3','facial_consistency':'face-v1'}

def profiles(overrides=None):
    base = {'max_duration_seconds':180}
    result = {}
    for name in VERSIONS:
        fps,width,cap = (8,640,1440) if name in ('optical_flow','facial_consistency') else (2,384,360)
        if name=='text_consistency':
            fps,width,cap = 2,1280,360
        prefix = name.upper()
        result[name] = dict(base,sample_fps=float(os.getenv(prefix+'_FPS',fps)),
                            frame_width=int(os.getenv(prefix+'_WIDTH',width)),max_frames=cap)
        if overrides:
            result[name].update(overrides)
    return result

def contract(overrides=None):
    ref=os.getenv('ANOMALY_REFERENCE_PATH','')
    ref_hash=hashlib.sha256(Path(ref).read_bytes()).hexdigest() if ref and Path(ref).is_file() else None
    face=os.getenv('FACE_MODEL_PATH','')
    face_hash=hashlib.sha256(Path(face).read_bytes()).hexdigest() if face and Path(face).is_file() else None
    return {'reference_hash':ref_hash,'face_model_hash':face_hash,'code_version':'v4','analyzers':VERSIONS,'profiles':profiles(overrides),
            'ocr':ENABLE_OCR,'depth':ENABLE_DEPTH,'depth_model':DEPTH_MODEL if ENABLE_DEPTH else None,
            'face_model':os.getenv('FACE_MODEL_PATH',''), 'face_enabled':os.getenv('ENABLE_FACE','0')=='1'}
