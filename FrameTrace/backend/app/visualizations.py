"""Save actual frame/flow diagnostics for the dashboard. Never synthetic test results."""
from pathlib import Path
import cv2
import numpy as np
from .config import ENABLE_DEPTH


def save_visuals(frames, output_dir):
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    saved = []
    if cv2.imwrite(str(target / 'first_frame.jpg'), frames[0].bgr):
        saved.append('first_frame')
    if len(frames) >= 2:
        a = cv2.cvtColor(frames[0].bgr, cv2.COLOR_BGR2GRAY)
        b = cv2.cvtColor(frames[1].bgr, cv2.COLOR_BGR2GRAY)
        flow = cv2.calcOpticalFlowFarneback(a, b, None, .5, 3, 21, 3, 5, 1.2, 0)
        magnitude, angle = cv2.cartToPolar(flow[..., 0], flow[..., 1])
        hsv = np.zeros((*magnitude.shape, 3), dtype=np.uint8)
        hsv[..., 0] = (angle / 2 * 180 / np.pi).astype(np.uint8)
        hsv[..., 1] = 255
        # Fixed scaling exposes motion strength, rather than per-frame auto-normalization.
        hsv[..., 2] = np.clip(magnitude * 20, 0, 255).astype(np.uint8)
        visual = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
        if cv2.imwrite(str(target / 'optical_flow.jpg'), visual):
            saved.append('optical_flow')
    # Deterministic diagnostic enhancements; not separate sources of evidence.
    src = frames[0].bgr
    rgb = cv2.cvtColor(src, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    gamma_light = np.clip(rgb ** .45 * 255, 0, 255).astype(np.uint8)
    if cv2.imwrite(str(target / 'gamma_shadows.jpg'), cv2.cvtColor(gamma_light, cv2.COLOR_RGB2BGR)):
        saved.append('gamma_shadows')
    hsv = cv2.cvtColor(src, cv2.COLOR_BGR2HSV)
    boosted = hsv.copy()
    boosted[..., 1] = np.clip(hsv[..., 1].astype(np.float32) * 1.8, 0, 255).astype(np.uint8)
    if cv2.imwrite(str(target / 'saturation_boost.jpg'), cv2.cvtColor(boosted, cv2.COLOR_HSV2BGR)):
        saved.append('saturation_boost')
    if ENABLE_DEPTH:
        try:
            from .detectors.depth import estimate_depth
            depth = estimate_depth(frames[0].bgr)
            bottom, top = np.percentile(depth, [5, 95])
            normalized = np.uint8(np.clip((depth-bottom)/(max(top-bottom, 1e-6)),0,1)*255)
            vis = cv2.applyColorMap(normalized, cv2.COLORMAP_TURBO)
            if cv2.imwrite(str(target / 'depth_map.jpg'), vis):
                saved.append('depth_map')
        except Exception:
            # Detector status already reports depth errors; don't replace analysis result.
            pass
    return saved
