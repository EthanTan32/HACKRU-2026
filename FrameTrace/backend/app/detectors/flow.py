"""Confidence-filtered, camera-compensated temporal motion diagnostics."""
import cv2
import numpy as np
from .common import response

VERSION = 'flow-v4'


def track(a, b, points):
    q, status, error = cv2.calcOpticalFlowPyrLK(a, b, points, None, winSize=(21,21), maxLevel=3)
    if q is None:
        return None
    back, bs, _ = cv2.calcOpticalFlowPyrLK(b, a, q, None, winSize=(21,21), maxLevel=3)
    if back is None:
        return None
    p, q, back = (x.reshape(-1,2) for x in (points,q,back))
    fb = np.linalg.norm(p-back, axis=1)
    h,w = b.shape
    valid = ((status.ravel()==1) & (bs.ravel()==1) & (error.ravel()<30) &
             (fb<1.5) & np.isfinite(q).all(axis=1) &
             (q[:,0]>=2) & (q[:,0]<w-2) & (q[:,1]>=2) & (q[:,1]<h-2))
    return q, valid, fb


def residual_velocity(p, q, dt, diagonal):
    matrix, inliers = cv2.estimateAffine2D(p, q, method=cv2.RANSAC, ransacReprojThreshold=2)
    if matrix is None or inliers is None or inliers.mean()<.35:
        return None
    prediction = p @ matrix[:,:2].T + matrix[:,2]
    return (q-prediction)/(dt*diagonal), float(inliers.mean())


def local_discontinuity(points, acceleration):
    # Nearby points in one moving object may accelerate together; score departure
    # from that local motion, not foreground motion itself. Parallax is locally smooth.
    distances = np.linalg.norm(points[:,None]-points[None,:], axis=-1)
    neighbors = np.argsort(distances, axis=1)[:,1:9]
    local = np.median(acceleration[neighbors], axis=1)
    return np.linalg.norm(acceleration-local, axis=1)


def analyze(frames):
    segments, best_overlay = [], None
    best_raw = -1
    for a,b,c in zip(frames,frames[1:],frames[2:]):
        dt1,dt2 = b.time-a.time,c.time-b.time
        if min(dt1,dt2)<=0 or max(dt1,dt2)>.35:
            continue  # sparse observations cannot establish trajectory continuity
        ga,gb,gc = [cv2.cvtColor(f.bgr,cv2.COLOR_BGR2GRAY) for f in (a,b,c)]
        p = cv2.goodFeaturesToTrack(ga, maxCorners=600, qualityLevel=.015, minDistance=6)
        if p is None:
            continue
        first = track(ga,gb,p)
        if first is None:
            continue
        q,valid1,fb1 = first
        second = track(gb,gc,q.astype(np.float32).reshape(-1,1,2))
        if second is None:
            continue
        r,valid2,fb2 = second
        valid = valid1 & valid2
        if valid.sum()<24:
            continue
        p,q,r = p.reshape(-1,2)[valid],q[valid],r[valid]
        diagonal = float(np.hypot(*ga.shape))
        v1 = residual_velocity(p,q,dt1,diagonal)
        v2 = residual_velocity(q,r,dt2,diagonal)
        if v1 is None or v2 is None:
            continue
        acceleration = (v2[0]-v1[0])/((dt1+dt2)/2)
        local = local_discontinuity(q,acceleration)
        raw = float(np.percentile(local,90))
        segments.append({'timestamp':b.time,'raw_value':raw,'valid_tracks':int(valid.sum()),
                         'confidence':float(valid.mean()*min(v1[1],v2[1])),
                         'fb_error_px':float(np.median(np.maximum(fb1,fb2)[valid])),
                         'acceleration':float(np.percentile(np.linalg.norm(acceleration,axis=1),90))})
        if raw > best_raw:
            best_overlay=(b.bgr,q,local)
            best_raw=raw
    metrics = {'triplets_analyzed':len(segments)}
    if len(segments)<2:
        return response('optical_flow','insufficient_data',metrics=metrics,
                        note='Need reliable adjacent tracks at 6–12 FPS; blur, occlusion and cuts reduce evidence.')
    metrics.update(median_p90_relative_velocity_change=float(np.median([s['acceleration'] for s in segments])),
                   median_local_deformation=float(np.median([s['raw_value'] for s in segments])),
                   confidence=float(np.mean([s['confidence'] for s in segments])),
                   valid_observations=sum(s['valid_tracks'] for s in segments))
    result = response('optical_flow','ok',metrics=metrics,
                      note='Raw local acceleration after RANSAC camera compensation. Index/flags require held-out reference calibration; physical deformation can also raise measurements.')
    result['segments'] = segments
    # Private visualization data removed by pipeline before JSON serialization.
    index = int(np.argmax([s['raw_value'] for s in segments]))
    frame,points,values = best_overlay
    overlay = frame.copy()
    for point,value in zip(points,values):
        intensity = int(255*value/(value+max(segments[index]['raw_value'],1e-8)))
        cv2.circle(overlay,tuple(np.round(point).astype(int)),3,(0,255-intensity,intensity),-1)
    result['_overlay'] = overlay
    return result
