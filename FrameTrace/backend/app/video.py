from dataclasses import dataclass
import math
import cv2
from .config import FRAME_WIDTH, SAMPLE_FPS, MAX_FRAMES, MAX_DURATION_SECONDS


@dataclass
class Frame:
    time: float
    bgr: object


def inspect_video(path, max_duration_seconds=MAX_DURATION_SECONDS):
    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            raise ValueError('Could not decode the uploaded video')
        fps = cap.get(cv2.CAP_PROP_FPS)
        count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        if fps <= 0 or fps > 1000 or count <= 0:
            raise ValueError('Invalid or unsupported video metadata')
        duration = count / fps
        if max_duration_seconds is not None and duration > max_duration_seconds:
            raise ValueError(f'Videos must be {max_duration_seconds} seconds or shorter')
        if duration <= 0:
            raise ValueError('Empty video')
        return {'fps': fps, 'duration': duration, 'frames': count}
    finally:
        cap.release()


def sample_frames(path, *, sample_fps=None, max_frames=None, frame_width=None,
                  max_duration_seconds=MAX_DURATION_SECONDS):
    """Stream decoded frames, retaining at most max_frames resized images in memory."""
    sample_fps = SAMPLE_FPS if sample_fps is None else sample_fps
    max_frames = MAX_FRAMES if max_frames is None else max_frames
    frame_width = FRAME_WIDTH if frame_width is None else frame_width
    if sample_fps <= 0 or max_frames < 3 or frame_width < 64:
        raise ValueError('Invalid sampling options')
    info = inspect_video(path, max_duration_seconds=max_duration_seconds)
    cap = cv2.VideoCapture(str(path))
    frames = []
    stride = max(1, round(info['fps'] / sample_fps), math.ceil(info['frames'] / max_frames))
    frame_index = 0
    previous_time = -1.0
    try:
        while len(frames) < max_frames:
            ok, bgr = cap.read()
            if not ok:
                break
            if frame_index % stride == 0:
                height, width = bgr.shape[:2]
                if width > frame_width:
                    scale = frame_width / width
                    bgr = cv2.resize(bgr, (frame_width, round(height * scale)))
                decoder_time = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
                timestamp = decoder_time if math.isfinite(decoder_time) and decoder_time > previous_time else frame_index / info['fps']
                if timestamp <= previous_time:
                    timestamp = previous_time + stride / info['fps']
                frames.append(Frame(time=timestamp, bgr=bgr))
                previous_time = timestamp
            frame_index += 1
    finally:
        cap.release()
    if len(frames) < 3:
        raise ValueError('Need at least 3 sampled frames to analyze motion')
    return frames, info
