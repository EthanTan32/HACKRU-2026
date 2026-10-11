import numpy as np


def response(name, status, score=None, events=None, metrics=None, note=''):
    return {
        'name': name, 'status': status,
        # scores are heuristic anomaly indices until evaluated/calibrated, NOT P(AI)
        'anomaly_index': None if score is None else round(float(score), 4),
        'events': events or [], 'metrics': metrics or {}, 'note': note,
    }


def robust_index(values, scale):
    """Convenient dashboard visualization index, not trained or calibrated."""
    vals = np.asarray(values, dtype=float)
    vals = vals[np.isfinite(vals)]
    if not len(vals):
        return None
    return float(np.clip(np.median(vals) / scale, 0, 1))
