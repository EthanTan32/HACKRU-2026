import cv2
import numpy as np
import pytest
from app.video import Frame
from app.detectors.flow import analyze, local_discontinuity, residual_velocity
from app.detectors.face import shape_error
from app.detectors.depth import relative_depth_warp_error


def sequence(mode):
    rng=np.random.default_rng(17)
    base=rng.integers(20,230,(180,320,3),dtype=np.uint8)
    base=cv2.GaussianBlur(base,(3,3),0)
    frames=[]
    for i in range(12):
        matrix=cv2.getRotationMatrix2D((160,90),i*.3 if mode=='rotation' else 0,1+i*.002 if mode=='zoom' else 1)
        matrix[:,2]+=[i*1.5,0]
        image=cv2.warpAffine(base,matrix,(320,180))
        if mode=='warp' and i%3==1:
            image[45:100,90:140]=np.roll(image[45:100,90:140],8,axis=1)
        frames.append(Frame(i/8,image))
    return frames


@pytest.mark.parametrize('mode',['pan','rotation','zoom'])
def test_camera_motion_not_saturated(mode):
    result=analyze(sequence(mode))
    assert result['status']=='ok'
    assert result['anomaly_index'] is None  # no invented calibration
    assert not result['events']
    assert result['metrics']['median_local_deformation']<.15


def test_geometric_warp_measurable():
    smooth=analyze(sequence('pan'))
    warped=analyze(sequence('warp'))
    assert warped['metrics']['median_local_deformation']>smooth['metrics']['median_local_deformation']*1.5


def test_foreground_acceleration_is_locally_coherent():
    y,x=np.mgrid[:12,:12]
    points=np.column_stack((x.ravel(),y.ravel())).astype(float)
    acceleration=np.zeros_like(points)
    acceleration[points[:,0]<6]=[2,1]
    smooth=local_discontinuity(points,acceleration)
    acceleration[65]=[30,-40]
    jumped=local_discontinuity(points,acceleration)
    assert np.median(smooth)==0
    assert jumped[65]>40


def test_sparse_blur_occlusion_insufficient():
    frames=[Frame(i,np.zeros((180,320,3),np.uint8)) for i in range(6)]
    assert analyze(frames)['status']=='insufficient_data'


def test_face_pose_expression_and_shape():
    rng=np.random.default_rng(21)
    face=rng.normal(size=(478,3))
    angle=.3
    rotation=np.array([[np.cos(angle),0,np.sin(angle)],[0,1,0],[-np.sin(angle),0,np.cos(angle)]])
    turned=face@rotation*1.5+[2,3,4]
    # Smiles and blinks affect expression landmarks, not stable shape.
    turned[[13,14,159,145]]+=.3
    assert shape_error(face,turned)<1e-10
    turned[168]+=[.5,.5,0]
    assert shape_error(face,turned)>1e-4


def test_depth_scale_offset_alignment():
    rng=np.random.default_rng(13)
    image=rng.integers(20,230,(120,180,3),dtype=np.uint8)
    y,x=np.mgrid[:120,:180]
    depth=(x+y*.4).astype(np.float32)
    error=relative_depth_warp_error(image,image,depth,depth*2+5)
    assert error is not None and error<1e-4

def test_depth_textureless_is_not_evidence():
    image=np.zeros((120,180,3),np.uint8)
    depth=np.ones((120,180),np.float32)
    assert relative_depth_warp_error(image,image,depth,depth) is None


def test_reference_calibration_separates_raw_and_probability(tmp_path,monkeypatch):
    import json
    from app.anomaly_calibration import apply
    path=tmp_path/'reference.json'
    path.write_text(json.dumps({'version':'v4','optical_flow':list(np.linspace(0,.1,100))}),encoding='utf8')
    monkeypatch.setenv('ANOMALY_REFERENCE_PATH',str(path))
    result={'name':'optical_flow','segments':[{'timestamp':1,'raw_value':.02,'confidence':.9},
                                            {'timestamp':2,'raw_value':.3,'confidence':.9}]}
    apply(result)
    assert result['segments'][0]['anomaly_index']<.3
    assert len(result['events'])==1
    assert result['events'][0]['timestamp']==2
    assert 'ai_probability' not in result


def test_natural_foreground_and_parallax_raw_residual():
    rng=np.random.default_rng(22)
    bg=cv2.GaussianBlur(rng.integers(15,235,(180,320,3),dtype=np.uint8),(3,3),0)
    person=bg[30:130,80:140].copy()
    frames=[]
    for i in range(12):
        image=cv2.warpAffine(bg,np.float32([[1,0,i],[0,1,0]]),(320,180))
        # One independently walking foreground region against a panning background.
        x=80+i*2
        image[30:130,x:x+60]=person
        frames.append(Frame(i/8,image))
    result=analyze(frames)
    assert result['status']=='ok'
    assert result['metrics']['median_local_deformation']<.3
