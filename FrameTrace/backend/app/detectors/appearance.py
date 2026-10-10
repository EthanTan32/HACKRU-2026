"""Temporal brightness/chroma consistency under optical-flow alignment.

Gamma and saturation adjustments are diagnostic views of the same measurements,
not independent evidence or recovery of hidden information. Score = anomalous
appearance changes AFTER motion and coarse exposure/saturation correction.
"""
import cv2
import numpy as np
from .common import response, robust_index


def aligned_appearance_error(bgr_a, bgr_b):
    """Return dimensionless brightness/chroma residuals or None when alignment fails.

    Photometric anomalies can arise from real shadows, sensor processing, motion,
    compression, lighting, or occlusion. This is NOT a synthetic-media classifier.
    """
    if bgr_a.shape != bgr_b.shape:
        return None
    a = cv2.resize(bgr_a, (min(384, bgr_a.shape[1]),
                              round(bgr_a.shape[0] * min(384, bgr_a.shape[1]) / bgr_a.shape[1])))
    b = cv2.resize(bgr_b, (a.shape[1], a.shape[0]))
    gray_a = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
    gray_b = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)
    fwd = cv2.calcOpticalFlowFarneback(gray_a, gray_b, None, .5, 3, 21, 3, 5, 1.2, 0)
    back = cv2.calcOpticalFlowFarneback(gray_b, gray_a, None, .5, 3, 21, 3, 5, 1.2, 0)
    h, w = gray_a.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    map_x, map_y = xx + fwd[..., 0], yy + fwd[..., 1]
    back_warped = cv2.remap(back, map_x, map_y, cv2.INTER_LINEAR,
                             borderMode=cv2.BORDER_CONSTANT)
    flow_error = np.linalg.norm(fwd + back_warped, axis=2)
    valid = ((map_x >= 2) & (map_x < w - 2) & (map_y >= 2) &
             (map_y < h - 2) & (flow_error < 1.5))
    # Exclude edges where a tiny correspondence error gives a large color error.
    gradients = cv2.Laplacian(gray_a, cv2.CV_32F)
    limit = np.percentile(np.abs(gradients), 75)
    valid &= np.abs(gradients) <= max(limit, 2)
    if valid.sum() < 400 or valid.mean() < .1:
        return None

    a_hsv = cv2.cvtColor(a.astype(np.float32) / 255, cv2.COLOR_BGR2HSV)
    warped_b = cv2.remap(b, map_x, map_y, cv2.INTER_LINEAR,
                         borderMode=cv2.BORDER_CONSTANT)
    b_hsv = cv2.cvtColor(warped_b.astype(np.float32) / 255, cv2.COLOR_BGR2HSV)
    v1, v2 = a_hsv[..., 2], b_hsv[..., 2]
    s1, s2 = a_hsv[..., 1], b_hsv[..., 1]
    # Estimate global automatic exposure correction on adequately-lit points.
    lit = valid & (v1 > .12) & (v2 > .12) & (v1 < .95) & (v2 < .95)
    if lit.sum() < 200:
        return None
    exposure_ratio = np.clip(np.median(v2[lit] / np.maximum(v1[lit], .02)), .5, 2.)
    v2 = np.clip(v2 / exposure_ratio, 0, 1)
    stable = valid & (v1 > .1) & (v2 > .1)
    if stable.sum() < 200:
        return None
    # Equalized gamma diagnostics: shadow-sensitive and highlight-sensitive.
    shadow = float(np.percentile(np.abs(np.sqrt(v1[stable]) - np.sqrt(v2[stable])), 85))
    highlight = float(np.percentile(np.abs(v1[stable]**1.8 - v2[stable]**1.8), 85))
    colorful = stable & (np.maximum(s1, s2) > .12)
    if colorful.sum() >= 200:
        # Subtract coherent/global saturation response, focus on local changes.
        ds = s2[colorful] - s1[colorful]
        chroma = float(np.percentile(np.abs(ds - np.median(ds)), 85))
    else:
        chroma = None
    return {'shadow_gamma_p85': shadow, 'highlight_gamma_p85': highlight,
            'saturation_p85': chroma, 'valid_fraction': float(stable.mean()),
            'exposure_ratio': float(exposure_ratio)}


def analyze(frames):
    measures, events = [], []
    # Restrict CPU-heavy dense flow to every other sampled frame pair.
    for a, b in zip(frames[::2], frames[2::2]):
        values = aligned_appearance_error(a.bgr, b.bgr)
        if values is None:
            continue
        score = max(values['shadow_gamma_p85'], values['highlight_gamma_p85'],
                    values['saturation_p85'] or 0.0)
        measures.append(values)
        if score > .23:
            events.append({'timestamp': b.time, 'type': 'appearance_instability',
                           'severity': round(float(min(score / .5, 1)), 3),
                           'detail': (f'Gamma residuals {values["shadow_gamma_p85"]:.3f}/'
                                      f'{values["highlight_gamma_p85"]:.3f}; '
                                      f'saturation residual {values["saturation_p85"] or 0:.3f}')})
    if len(measures) < 2:
        return response('color_consistency', 'insufficient_data',
                        note='Too few optical-flow-aligned, visible color regions')
    def median(key):
        vals = [m[key] for m in measures if m[key] is not None]
        return round(float(np.median(vals)), 5) if vals else None
    combined = [max(m['shadow_gamma_p85'], m['highlight_gamma_p85'],
                    m['saturation_p85'] or 0) for m in measures]
    return response('color_consistency', 'ok', robust_index(combined, .4), events,
                    {'pairs_analyzed': len(measures),
                     'median_shadow_gamma_p85': median('shadow_gamma_p85'),
                     'median_highlight_gamma_p85': median('highlight_gamma_p85'),
                     'median_saturation_p85': median('saturation_p85'),
                     'median_valid_fraction': median('valid_fraction')},
                    'Gamma/saturation views expose brightness and chroma differences; '
                    'real exposure shifts, lighting, motion, and compression can cause them.')
