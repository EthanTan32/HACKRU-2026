import cv2
import numpy as np


def match_features(bgr_a, bgr_b):
    gray_a = cv2.cvtColor(bgr_a, cv2.COLOR_BGR2GRAY)
    gray_b = cv2.cvtColor(bgr_b, cv2.COLOR_BGR2GRAY)
    corners = cv2.goodFeaturesToTrack(gray_a, maxCorners=500, qualityLevel=0.015,
                                     minDistance=8, blockSize=7)
    if corners is None or len(corners) < 12:
        return None
    next_pts, status, _ = cv2.calcOpticalFlowPyrLK(gray_a, gray_b, corners, None)
    if next_pts is None:
        return None
    previous_back, back_status, _ = cv2.calcOpticalFlowPyrLK(gray_b, gray_a, next_pts, None)
    if previous_back is None:
        return None
    before = corners.reshape(-1, 2)
    after = next_pts.reshape(-1, 2)
    back = previous_back.reshape(-1, 2)
    valid = ((status.reshape(-1) == 1) & (back_status.reshape(-1) == 1) &
             (np.linalg.norm(before - back, axis=1) < 1.5))
    if valid.sum() < 12:
        return None
    return before[valid], after[valid]


def estimate_scene_motion(bgr_a, bgr_b):
    pair = match_features(bgr_a, bgr_b)
    if pair is None:
        return None
    before, after = pair
    matrix, inliers = cv2.findHomography(before, after, cv2.RANSAC, 3.0)
    if matrix is None or inliers is None:
        return None
    predicted = cv2.perspectiveTransform(before.reshape(-1, 1, 2), matrix).reshape(-1, 2)
    return {
        'before': before, 'after': after, 'predicted': predicted,
        'inliers': inliers.ravel().astype(bool), 'matrix': matrix,
        'camera_motion_px': float(np.median(np.linalg.norm(predicted - before, axis=1))),
    }
