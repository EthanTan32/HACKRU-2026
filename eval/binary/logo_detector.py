"""
Video Logo and Visible Watermark Detector
Analyzes temporal pixel persistence, stationary gradient fields (Dekel et al. formulation),
and spatial corner priors to detect opaque and semi-transparent logos in video streams.
"""

import os
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np


class LogoDetector:
    """
    Detects persistent static and semi-transparent logos/watermarks in video frames.
    """

    def __init__(
        self,
        max_samples: int = 120,
        corner_margin_x: float = 0.25,
        corner_margin_y: float = 0.22,
        min_area_ratio: float = 0.0003,
        max_area_ratio: float = 0.18,
        confidence_threshold: float = 0.35,
    ):
        self.max_samples = max_samples
        self.corner_margin_x = corner_margin_x
        self.corner_margin_y = corner_margin_y
        self.min_area_ratio = min_area_ratio
        self.max_area_ratio = max_area_ratio
        self.confidence_threshold = confidence_threshold

    def detect_in_video(
        self,
        video_path: str,
        output_annotated_frame: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Processes a video file to detect static and semi-transparent logos.
        """
        if not os.path.exists(video_path):
            return {
                "detected": False,
                "error": f"Video not found: {video_path}",
                "watermarks": [],
            }

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return {
                "detected": False,
                "error": f"Failed to open video: {video_path}",
                "watermarks": [],
            }

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # Sample frames evenly across duration
        step = max(1, total_frames // self.max_samples) if total_frames > 0 else 1
        frames_gray: List[np.ndarray] = []
        grad_x_list: List[np.ndarray] = []
        grad_y_list: List[np.ndarray] = []
        last_color_frame: Optional[np.ndarray] = None

        frame_idx = 0
        while cap.isOpened() and len(frames_gray) < self.max_samples:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % step == 0:
                last_color_frame = frame.copy()
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
                frames_gray.append(gray)

                # Compute spatial Sobel gradients
                gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
                gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
                grad_x_list.append(gx)
                grad_y_list.append(gy)

            frame_idx += 1
        cap.release()

        if len(frames_gray) < 5:
            return {
                "detected": False,
                "warning": f"Insufficient frames sampled ({len(frames_gray)})",
                "watermarks": [],
                "watermark_count": 0,
                "frame_count": len(frames_gray),
            }

        h, w = frames_gray[0].shape
        frames_arr = np.array(frames_gray)  # Shape: (T, H, W)

        # 1. Temporal Standard Deviation (low where static overlays sit)
        temporal_std = np.std(frames_arr, axis=0)
        ambient_std = float(np.median(temporal_std))
        is_static_scene = ambient_std < 1.0

        # 2. Median Gradient Field (filters dynamic background motion)
        med_gx = np.median(np.array(grad_x_list), axis=0)
        med_gy = np.median(np.array(grad_y_list), axis=0)
        persistent_edge_mag = np.sqrt(med_gx**2 + med_gy**2)

        # 3. Spatial Priors (Corners and Borders)
        roi_mask = self._build_spatial_prior(h, w)

        # Normalize edge magnitude and stability
        p99_edges = max(float(np.percentile(persistent_edge_mag, 99)), 1e-5)
        norm_edges = np.clip(persistent_edge_mag / p99_edges, 0.0, 1.0)

        p95_std = max(float(np.percentile(temporal_std, 95)), 1e-5)
        # In static scenes (slides), temporal stability is uniform and uninformative
        if is_static_scene:
            temporal_stability = np.full((h, w), 0.5, dtype=np.float32)
        else:
            temporal_stability = np.clip(1.0 - (temporal_std / p95_std), 0.0, 1.0)

        # Watermark Saliency
        saliency_map = norm_edges * (temporal_stability ** 1.5) * roi_mask

        # 4. Extract Candidate Bounding Boxes
        watermarks = self._extract_watermark_candidates(
            saliency_map, temporal_std, persistent_edge_mag, h, w, is_static_scene=is_static_scene
        )

        # Filter by confidence threshold and minimum opacity
        # Watermarks/logos must possess measurable opacity (alpha >= 0.15); alpha ~= 0 means normal transparent background
        valid_watermarks = [
            w for w in watermarks
            if w["confidence"] >= self.confidence_threshold and (w["estimated_alpha"] >= 0.15 or is_static_scene)
        ]

        # 5. Optionally annotate frame
        annotated_path = None
        if output_annotated_frame and last_color_frame is not None and valid_watermarks:
            annotated_frame = self._draw_watermarks(last_color_frame, valid_watermarks)
            os.makedirs(os.path.dirname(os.path.abspath(output_annotated_frame)), exist_ok=True)
            cv2.imwrite(output_annotated_frame, annotated_frame)
            annotated_path = output_annotated_frame

        return {
            "detected": len(valid_watermarks) > 0,
            "watermark_count": len(valid_watermarks),
            "watermarks": valid_watermarks,
            "sampled_frames": len(frames_gray),
            "video_dimensions": [w, h],
            "fps": round(float(fps), 2),
            "annotated_frame": annotated_path,
        }

    def _build_spatial_prior(self, h: int, w: int) -> np.ndarray:
        """
        Creates a prior weight matrix prioritizing 4 corners and borders,
        while still leaving modest sensitivity in the center.
        """
        mask = np.full((h, w), 0.25, dtype=np.float32)  # baseline sensitivity everywhere
        mx = int(w * self.corner_margin_x)
        my = int(h * self.corner_margin_y)

        # Corner zones receive full weight (1.0)
        mask[0:my, 0:mx] = 1.0             # Top-Left
        mask[0:my, w - mx:w] = 1.0         # Top-Right
        mask[h - my:h, 0:mx] = 1.0         # Bottom-Left
        mask[h - my:h, w - mx:w] = 1.0     # Bottom-Right

        # Peripheral borders receive 0.7 weight
        mask[0:int(my * 0.7), :] = np.maximum(mask[0:int(my * 0.7), :], 0.75)
        mask[h - int(my * 0.7):h, :] = np.maximum(mask[h - int(my * 0.7):h, :], 0.75)
        return mask

    def _extract_watermark_candidates(
        self,
        saliency_map: np.ndarray,
        temporal_std: np.ndarray,
        edge_mag: np.ndarray,
        h: int,
        w: int,
        is_static_scene: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Morphologically thresholds saliency map to segment candidate bounding boxes.
        """
        non_zero = saliency_map[saliency_map > 0.05]
        if len(non_zero) == 0:
            return []

        # Adaptive thresholding
        threshold = float(np.percentile(non_zero, 80))
        binary = (saliency_map >= threshold).astype(np.uint8) * 255

        # Morphological closing to connect characters and fragmented icons
        k_size_x = max(7, int(w * 0.015))
        k_size_y = max(7, int(h * 0.015))
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k_size_x, k_size_y))
        closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates: List[Dict[str, Any]] = []

        total_area = float(h * w)
        min_area = total_area * self.min_area_ratio
        max_area = total_area * self.max_area_ratio
        ambient_std = max(float(np.median(temporal_std)), 1e-5)
        p95_edge = max(float(np.percentile(edge_mag, 95)), 1e-5)

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < min_area or area > max_area:
                continue

            x, y, bw, bh = cv2.boundingRect(cnt)
            if bw < 4 or bh < 4:
                continue

            roi_saliency = saliency_map[y:y + bh, x:x + bw]
            roi_std = temporal_std[y:y + bh, x:x + bw]
            roi_edge = edge_mag[y:y + bh, x:x + bw]

            # Confidence based on peak saliency and persistent edge density
            conf = float(np.mean(roi_saliency[roi_saliency > 0])) if np.any(roi_saliency > 0) else 0.0
            edge_density = float(np.mean(roi_edge)) / p95_edge

            # Opacity (alpha) estimation:
            if is_static_scene:
                # In static scenes, temporal attenuation cannot be reliably measured
                est_alpha = 0.50
                conf = conf * 0.6  # Penalize static background false positives
                wm_type = "static_overlay"
            else:
                std_ratio = float(np.median(roi_std)) / ambient_std
                est_alpha = max(0.0, min(1.0, 1.0 - np.sqrt(min(1.0, std_ratio))))
                wm_type = "opaque_logo" if est_alpha > 0.8 else "semi_transparent_watermark"

            # Determine region label
            region = self._classify_region(x, y, bw, bh, w, h)

            candidates.append({
                "bbox": [int(x), int(y), int(bw), int(bh)],
                "area_pixels": int(area),
                "area_percentage": round(float(area / total_area) * 100.0, 3),
                "region": region,
                "estimated_alpha": round(float(est_alpha), 2),
                "type": wm_type,
                "confidence": round(float(conf), 3),
                "edge_density": round(float(min(1.0, edge_density)), 3),
            })

        # Sort descending by confidence
        candidates.sort(key=lambda item: item["confidence"], reverse=True)
        return candidates

    def _classify_region(self, x: int, y: int, bw: int, bh: int, w: int, h: int) -> str:
        """Classifies bounding box location into a named region."""
        cx = x + bw / 2.0
        cy = y + bh / 2.0

        vert = "top" if cy < h * 0.35 else ("bottom" if cy > h * 0.65 else "mid")
        horiz = "left" if cx < w * 0.35 else ("right" if cx > w * 0.65 else "center")
        if vert == "mid" and horiz == "center":
            return "center"
        return f"{vert}_{horiz}"

    def _draw_watermarks(self, frame: np.ndarray, watermarks: List[Dict[str, Any]]) -> np.ndarray:
        """Renders bounding boxes and labels onto the frame."""
        vis = frame.copy()
        for wm in watermarks:
            x, y, bw, bh = wm["bbox"]
            label = f"{wm['type']} ({wm['confidence']:.2f}, a={wm['estimated_alpha']:.2f})"
            color = (0, 0, 255) if wm["type"] == "opaque_logo" else (255, 140, 0)
            cv2.rectangle(vis, (x, y), (x + bw, y + bh), color, 2)
            cv2.putText(vis, label, (x, max(15, y - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
        return vis

