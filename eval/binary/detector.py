"""
Video Authenticity Detector
Evaluates a video by executing both C2PA validation and stationary logo detection.
"""

from typing import Any, Dict, Optional

try:
    from .c2pa2_checker import check_c2pa
    from .logo_detector import LogoDetector
except ImportError:
    try:
        from c2pa2_checker import check_c2pa
        from logo_detector import LogoDetector
    except ImportError:
        from eval.binary.c2pa2_checker import check_c2pa
        from eval.binary.logo_detector import LogoDetector


def detect(
    video_path: str,
    max_samples: int = 80,
    output_annotated_frame: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Runs both C2PA validation and stationary logo detection on a video.

    Args:
        video_path: Path to target video file.
        max_samples: Maximum frames to sample for logo persistence.
        output_annotated_frame: Optional path to save an annotated frame image.

    Returns:
        dict:
            - 'c2pa': C2PA return code (-1: unopenable, 0: validated, 1: no header/invalid)
            - 'logo': Detection dictionary from LogoDetector
    """
    c2pa_status = check_c2pa(video_path)
    logo_results = LogoDetector(max_samples=max_samples).detect_in_video(
        video_path, output_annotated_frame=output_annotated_frame
    )

    return {
        "c2pa": c2pa_status,
        "logo": logo_results,
    }


class VideoInspector:
    """Wrapper class providing an object-oriented interface."""

    def __init__(self, sample_frames: int = 80):
        self.sample_frames = sample_frames

    def inspect(
        self,
        video_path: str,
        output_annotated_frame: Optional[str] = None,
    ) -> Dict[str, Any]:
        return detect(
            video_path,
            max_samples=self.sample_frames,
            output_annotated_frame=output_annotated_frame,
        )

