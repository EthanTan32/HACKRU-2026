"""Single versioned feature contract across extraction, training, and inference.

Raw metrics stay separate: for example gamma/shadow and saturation are distinct
features so the supervised classifier can learn different weights for them.
"""
DETECTOR_NAMES = {
    'text_consistency': 'text',
    'background_motion': 'background',
    'depth_consistency': 'depth',
    'optical_flow': 'flow',
    'color_consistency': 'color',
    'facial_consistency': 'face',
}
RAW_METRICS = {
    'face_shape_residual': ('facial_consistency', 'median_shape_residual'),
    'face_flow_residual': ('facial_consistency', 'median_local_flow_residual'),
    'face_observations': ('facial_consistency', 'valid_observations'),
    'face_confidence': ('facial_consistency', 'confidence'),
    'face_eye_aperture': ('facial_consistency', 'median_eye_aperture'),
    'face_mouth_opening': ('facial_consistency', 'median_mouth_opening'),
    'flow_local_deformation': ('optical_flow', 'median_local_deformation'),
    'flow_confidence': ('optical_flow', 'confidence'),
    'flow_observations': ('optical_flow', 'valid_observations'),
    'text_stable_tracks': ('text_consistency', 'stable_text_tracks'),
    'text_confirmed_changes': ('text_consistency', 'confirmed_changes'),
    'background_p90_reprojection_px': ('background_motion', 'median_p90_reprojection_px'),
    'background_frozen_fraction': ('background_motion', 'median_frozen_candidate_fraction'),
    'depth_median_residual': ('depth_consistency', 'median_depth_residual'),
    'depth_valid_frame_pairs': ('depth_consistency', 'valid_frame_pairs'),
    'flow_relative_velocity_change': ('optical_flow', 'median_p90_relative_velocity_change'),
    'flow_triplets': ('optical_flow', 'triplets_analyzed'),
    'color_shadow_gamma_p85': ('color_consistency', 'median_shadow_gamma_p85'),
    'color_highlight_gamma_p85': ('color_consistency', 'median_highlight_gamma_p85'),
    'color_saturation_p85': ('color_consistency', 'median_saturation_p85'),
    'color_valid_fraction': ('color_consistency', 'median_valid_fraction'),
}
FEATURES = ([f'{short}_anomaly_index' for short in DETECTOR_NAMES.values()] +
            [f'{short}_available' for short in DETECTOR_NAMES.values()] +
            [f'{short}_insufficient' for short in DETECTOR_NAMES.values()] +
            [f'{short}_unavailable' for short in DETECTOR_NAMES.values()] +
            list(RAW_METRICS.keys()))
EXPORT_COLUMNS = (['video_path', 'source_id', 'generator', 'split', 'label',
                   'feature_signature', 'duration_seconds'] + FEATURES)


def vector_from_result(result):
    output = {}
    for detector_name, short in DETECTOR_NAMES.items():
        det = result['detectors'].get(detector_name, {})
        output[f'{short}_anomaly_index'] = det.get('anomaly_index')
        output[f'{short}_available'] = int(det.get('status') == 'ok')
        output[f'{short}_insufficient'] = int(det.get('status') == 'insufficient_data')
        output[f'{short}_unavailable'] = int(det.get('status') in {'not_enabled','not_available','error'})
    for feature_name, (name, metric) in RAW_METRICS.items():
        output[feature_name] = result['detectors'].get(name, {}).get('metrics', {}).get(metric)
    return output
