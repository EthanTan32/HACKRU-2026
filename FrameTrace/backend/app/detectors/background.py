import numpy as np
from .tracking import estimate_scene_motion
from .common import response, robust_index


def analyze(frames):
    events, residuals, frozen = [], [], []
    valid_pairs = 0
    for a, b in zip(frames, frames[1:]):
        motion = estimate_scene_motion(a.bgr, b.bgr)
        if motion is None:
            continue
        mask = motion['inliers']
        # Without semantic segmentation, the dominant plane/background is only a proxy.
        if mask.sum() < 15 or mask.mean() < .6:
            continue
        valid_pairs += 1
        errors = np.linalg.norm(motion['after'] - motion['predicted'], axis=1)
        # Exclude probable independently-moving foreground features for this metric.
        inlier_error = float(np.percentile(errors[mask], 90))
        residuals.append(inlier_error)
        predicted_flow = np.linalg.norm(motion['predicted'] - motion['before'], axis=1)
        observed_flow = np.linalg.norm(motion['after'] - motion['before'], axis=1)
        candidates = predicted_flow > 2.5
        frozen_fraction = float(np.mean(observed_flow[candidates] < 0.5)) if candidates.sum() >= 10 else 0.0
        frozen.append(frozen_fraction)
        if inlier_error > 2 or frozen_fraction > .3:
            events.append({'timestamp': b.time, 'type': 'scene_motion_mismatch',
                           'severity': round(float(min(1, max(inlier_error / 5, frozen_fraction))), 3),
                           'detail': f'90th percentile inlier reprojection error: {inlier_error:.1f}px'})
    if valid_pairs < 2:
        return response('background_motion', 'insufficient_data', note='No reliable dominant scene motion found')
    return response('background_motion', 'ok', robust_index(residuals, 5), events,
                    {'pairs_analyzed': valid_pairs, 'median_p90_reprojection_px': round(float(np.median(residuals)), 3),
                     'median_frozen_candidate_fraction': round(float(np.median(frozen)), 3)},
                    'Dominant-motion geometric residual; motion parallax and foreground can confound it.')
