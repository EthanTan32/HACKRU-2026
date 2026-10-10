"""Optional face geometry diagnostics; no identity embeddings are generated."""
import os
import cv2
import numpy as np
from .common import response

STABLE = [1,4,6,168,197,195,5,98,327,33,263,127,356]


def normalized_geometry(points):
    p = points[STABLE].astype(float)
    p -= p.mean(axis=0)
    return p/max(float(np.linalg.norm(p)),1e-8)


def shape_error(a,b):
    # 3D Procrustes removes rigid pose and scale; eye/mouth interior landmarks
    # excluded so blinking and speech do not constitute shape anomalies.
    a,b = normalized_geometry(a),normalized_geometry(b)
    u,_,vt = np.linalg.svd(b.T@a)
    rotation = u@vt
    if np.linalg.det(rotation)<0:
        u[:,-1]*=-1
        rotation=u@vt
    return float(np.median(np.linalg.norm(a-b@rotation,axis=1)))


def analyze(frames):
    if os.getenv('ENABLE_FACE','0')!='1':
        return response('facial_consistency','not_enabled',note='Install MediaPipe and configure ENABLE_FACE=1 and FACE_MODEL_PATH.')
    try:
        import mediapipe as mp
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision
        options = vision.FaceLandmarkerOptions(base_options=python.BaseOptions(model_asset_path=os.environ['FACE_MODEL_PATH']),
            running_mode=vision.RunningMode.VIDEO,num_faces=4,min_face_detection_confidence=.7,
            min_face_presence_confidence=.7,min_tracking_confidence=.7,
            output_face_blendshapes=True,output_facial_transformation_matrixes=True)
        model = vision.FaceLandmarker.create_from_options(options)
    except Exception as exc:
        return response('facial_consistency','not_available',note=f'Face Landmarker unavailable: {exc}')
    segments,previous,overlay = [],[],None
    with model:
        for frame in frames:
            rgb=cv2.cvtColor(frame.bgr,cv2.COLOR_BGR2RGB)
            detection=model.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB,data=rgb),int(round(frame.time*1000)))
            current=[]
            used=set()
            for idx,landmarks in enumerate(detection.face_landmarks):
                p=np.array([[l.x,l.y,l.z] for l in landmarks])
                center=p[:,:2].mean(axis=0)
                extent=np.ptp(p[:,:2],axis=0)
                h,w=frame.bgr.shape[:2]
                x0,y0=np.maximum(0,(p[:,:2].min(axis=0)*[w,h]).astype(int))
                x1,y1=np.minimum([w,h],(p[:,:2].max(axis=0)*[w,h]).astype(int))
                crop=frame.bgr[y0:y1,x0:x1]
                if crop.size==0 or min(crop.shape[:2])<40 or cv2.Laplacian(crop,cv2.CV_64F).var()<25:
                    continue
                pose=np.asarray(detection.facial_transformation_matrixes[idx])[:3,:3]
                u,_,vt=np.linalg.svd(pose); pose=u@vt
                candidates=[(np.linalg.norm(center-old[1]),j,old) for j,old in enumerate(previous) if j not in used]
                if candidates:
                    distance,j,old=min(candidates,key=lambda item:item[0])
                    ambiguous = sum(candidate[0] <= max(distance*1.5, .02) for candidate in candidates) > 1
                    dt=frame.time-old[0]
                    angle=np.arccos(np.clip((np.trace(old[3].T@pose)-1)/2,-1,1))
                    if not ambiguous and distance<max(float(extent.max())*.5,.03) and 0<dt<=.35 and angle<.35:
                        used.add(j)
                        error=shape_error(old[2],p)
                        # Eye aperture and mouth opening remain raw expression covariates.
                        eye=float(np.linalg.norm(p[159]-p[145])/max(np.linalg.norm(p[33]-p[133]),1e-8))
                        mouth=float(np.linalg.norm(p[13]-p[14])/max(np.linalg.norm(p[61]-p[291]),1e-8))
                        pts=(old[2][STABLE,:2]*[w,h]).astype(np.float32).reshape(-1,1,2)
                        from .flow import track
                        tracked=track(cv2.cvtColor(old[4],cv2.COLOR_BGR2GRAY),cv2.cvtColor(frame.bgr,cv2.COLOR_BGR2GRAY),pts)
                        if tracked is not None and tracked[1].sum()>=8:
                            good=tracked[1]
                            flow_error=float(np.median(np.linalg.norm(tracked[0][good]-p[STABLE,:2][good]*[w,h],axis=1))/max(extent[0]*w,1))
                            segments.append({'timestamp':frame.time,'raw_value':error,'eye_aperture':eye,
                                             'mouth_opening':mouth,'pose_change_radians':float(angle),
                                             'local_flow_residual':flow_error,'confidence':float(good.mean()),'valid_tracks':int(good.sum())})
                current.append((frame.time,center,p,pose,frame.bgr))
                overlay=frame.bgr.copy()
                for point in p[STABLE,:2]*[w,h]:
                    cv2.circle(overlay,tuple(point.astype(int)),2,(255,255,0),-1)
            previous=current
    metrics={'valid_observations':len(segments)}
    if len(segments)<3:
        return response('facial_consistency','insufficient_data',metrics=metrics,note='Too few confidently associated, sharp faces under moderate pose changes.')
    metrics.update(median_shape_residual=float(np.median([s['raw_value'] for s in segments])),
                   median_eye_aperture=float(np.median([s['eye_aperture'] for s in segments])),
                   median_mouth_opening=float(np.median([s['mouth_opening'] for s in segments])),
                   median_local_flow_residual=float(np.median([s['local_flow_residual'] for s in segments])),
                   confidence=float(np.mean([s['confidence'] for s in segments])))
    result=response('facial_consistency','ok',metrics=metrics,note='Pose-normalized stable facial geometry; eyes/mouth are expression covariates. No identity recognition. Raw measurements require validation calibration.')
    result['segments']=segments
    result['_overlay']=overlay
    return result
