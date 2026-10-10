"""Optional calibrated inference using a model trained offline on labeled features.

Joblib deserializes Python objects; load ONLY a model file you created/trust.
"""
from functools import lru_cache
import os
from pathlib import Path

from .config import SAMPLE_FPS, MAX_FRAMES, FRAME_WIDTH, ENABLE_DEPTH, ENABLE_OCR
from .features import FEATURES, vector_from_result
from .preprocessing import contract


@lru_cache(maxsize=2)
def load_model(path):
    import joblib
    return joblib.load(path)


def maybe_predict(result):
    path = os.getenv('CLASSIFIER_PATH', '')
    if not path:
        return {'classification': 'not_trained', 'ai_probability': None,
                'message': 'No trained classifier configured. Six diagnostic measurements only.'}
    if not Path(path).is_file():
        return {'classification': 'model_unavailable', 'ai_probability': None,
                'message': 'Configured classifier model file was not found.'}
    try:
        artifact = load_model(path)
        if artifact['features'] != FEATURES:
            raise ValueError('Classifier features do not match this application version')
        config = artifact.get('extraction_config')
        if config != result.get('extraction_config', contract()):
            raise ValueError('Analyzer/preprocessing contract differs; re-extract features and retrain')
        if config and 'sampling' in config:
            sampling = config.get('sampling', {})
            if any(sampling.get(key) != value for key, value in [
                    ('sample_fps', SAMPLE_FPS), ('max_frames', MAX_FRAMES),
                    ('frame_width', FRAME_WIDTH)]):
                raise ValueError('Sampling settings differ from training configuration')
            if config.get('ocr') != ENABLE_OCR or config.get('depth') != ENABLE_DEPTH:
                raise ValueError('Enabled ML analyzers differ from training configuration')
        features = vector_from_result(result)
        if sum(features[f'{prefix}_available'] for prefix in ('text','background','depth','flow','color','face')) < 3:
            return {'classification': 'insufficient_evidence', 'ai_probability': None,
                    'message': 'Fewer than three detectors yielded usable measurements.'}
        import pandas as pd
        vector = pd.DataFrame([features], columns=FEATURES)
        probability = float(artifact['model'].predict_proba(vector)[0, 1])
        return {'classification': ('uncertain' if .35 < probability < .65 else ('likely_ai' if probability >= .65 else 'likely_real')),
                'ai_probability': round(probability, 4),
                'message': ('Model prediction calibrated on validation examples; examine the '
                            'test metrics and suspicious timestamps. Not proof of origin.')}
    except Exception as exc:
        return {'classification': 'model_unavailable', 'ai_probability': None,
                'message': f'Classifier unavailable: {type(exc).__name__}: {exc}'}
