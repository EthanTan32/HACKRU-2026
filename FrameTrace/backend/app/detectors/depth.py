from functools import lru_cache
import cv2
import numpy as np
from PIL import Image
from .common import response, robust_index
from ..config import ENABLE_DEPTH, DEPTH_MODEL


@lru_cache(maxsize=1)
def get_depth_model():
    from transformers import pipeline
    return pipeline('depth-estimation', model=DEPTH_MODEL)


def estimate_depth(bgr):
    img = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    value = get_depth_model()(img)['predicted_depth']
    if hasattr(value, 'detach'):
        value = value.detach().cpu().numpy()
    arr = np.asarray(value, dtype=np.float32).squeeze()
    return cv2.resize(arr, (bgr.shape[1], bgr.shape[0]), interpolation=cv2.INTER_LINEAR)


def relative_depth_warp_error(frame_a, frame_b, depth_a, depth_b):
    """Diagnostic residual. Scale alignment cannot fully correct perspective/parallax."""
    gray_a = cv2.cvtColor(frame_a, cv2.COLOR_BGR2GRAY)
    gray_b = cv2.cvtColor(frame_b, cv2.COLOR_BGR2GRAY)
    fwd = cv2.calcOpticalFlowFarneback(gray_a, gray_b, None, .5, 3, 21, 3, 5, 1.2, 0)
    back = cv2.calcOpticalFlowFarneback(gray_b, gray_a, None, .5, 3, 21, 3, 5, 1.2, 0)
    h, w = gray_a.shape
    yy, xx = np.mgrid[:h, :w].astype(np.float32)
    map_x, map_y = xx + fwd[..., 0], yy + fwd[..., 1]
    warped = cv2.remap(depth_b, map_x, map_y, cv2.INTER_LINEAR,
                       borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    warped_back = cv2.remap(back, map_x, map_y, cv2.INTER_LINEAR)
    fb = np.linalg.norm(fwd + warped_back, axis=-1)
    magnitude = np.linalg.norm(fwd, axis=-1)
    texture = cv2.cornerMinEigenVal(gray_a, 3)
    valid = ((map_x >= 2) & (map_x < w-2) & (map_y >= 2) & (map_y < h-2) &
             (fb < 1 + .05*magnitude) & (texture > 1e-5) & np.isfinite(warped) & np.isfinite(depth_a))
    if valid.sum() < max(100, int(h*w*.02)) or valid.mean() < .02:
        return None
    # Fit robust global scale+offset between monocular relative depth estimates.
    a, b = depth_a[valid], warped[valid]
    amin, amax = np.percentile(a, [10, 90]); bmin, bmax = np.percentile(b, [10, 90])
    if min(amax-amin,bmax-bmin) < 1e-6:
        return None
    scale = max((bmax-bmin)/(amax-amin), 1e-6)
    offset = float(np.median(b - scale*a))
    # Iteratively reweight correspondence residuals; occluded points cannot
    # dominate the monocular scale/offset fit.
    design = np.column_stack((a, np.ones_like(a)))
    for _ in range(4):
        residual = b-(scale*a+offset)
        mad = max(float(np.median(np.abs(residual-np.median(residual)))),1e-6)
        weights = np.minimum(1, 1.345*mad/np.maximum(np.abs(residual),1e-6))
        scale,offset = np.linalg.lstsq(design*np.sqrt(weights[:,None]),b*np.sqrt(weights),rcond=None)[0]
    if scale <= 0:
        return None
    error = np.abs(scale*a + offset - b)
    iqr = max(float(np.percentile(b, 75)-np.percentile(b, 25)), 1e-6)
    return float(np.median(error)/iqr)


def analyze(frames):
    if not ENABLE_DEPTH:
        return response('depth_consistency', 'not_enabled',
                        note='Set ENABLE_DEPTH=1; install PyTorch + Transformers; model downloads on first use')
    try:
        get_depth_model()
    except Exception as exc:
        return response('depth_consistency', 'not_available', note=f'Depth model initialization failed: {exc}')
    # Only every third sampled frame; depth inference is expensive on CPU.
    subsample = frames
    errors, events, previous = [], [], None
    for f in subsample:
        try:
            depth = estimate_depth(f.bgr)
        except Exception as exc:
            return response('depth_consistency', 'error', note=f'Depth inference failed: {exc}')
        if previous is not None:
            prior_frame, prior_depth = previous
            err = relative_depth_warp_error(prior_frame.bgr, f.bgr, prior_depth, depth)
            if err is not None:
                errors.append(err)
                if err > .35:
                    events.append({'timestamp': f.time, 'type': 'relative_depth_warp_error',
                                   'severity': round(float(min(err,1)), 3),
                                   'detail': f'Normalized temporal depth residual: {err:.2f}'})
        previous = (f, depth)
    if len(errors) < 2:
        return response('depth_consistency', 'insufficient_data',
                        note='Too few valid depth correspondences (occlusion or rapid motion)')
    return response('depth_consistency', 'ok', robust_index(errors, 1.0), events,
                    {'valid_frame_pairs': len(errors), 'median_depth_residual': round(float(np.median(errors)), 4)},
                    'Relative monocular depth; residual can be caused by real parallax, camera motion, and occlusion.')
