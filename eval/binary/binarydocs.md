# Video Authenticity Inspector

Inspects videos for C2PA provenance credentials and stationary watermark / logo overlays.

---

## 1. Detector (`detector.py`)

Runs both C2PA verification and logo detection on a target video and returns the results of both.

### Usage
```python
from detector import detect

result = detect("video.mp4")
print(result["c2pa"])  # C2PA status code
print(result["logo"])  # Logo detection dictionary
```

### Return Format
```python
{
    "c2pa": 0,  # -1, 0, or 1
    "logo": {
        "detected": True,
        "watermark_count": 1,
        "watermarks": [
            {
                "type": "stationary_logo",
                "region": "top_right",
                "bbox": [x, y, w, h],
                "confidence": 0.85,
                "estimated_alpha": 0.90
            }
        ],
        "frames_analyzed": 60
    }
}
```

---

## 2. C2PA Checker (`c2pa2_checker.py`)

Extracts C2PA metadata from video containers (ISO-BMFF UUID boxes and EBML) and validates cryptographic authenticity against `c2patool` or the official `c2pa` SDK.

### Core Functions

* **`check_c2pa(file_path: str) -> int`**
  Main validation function.
  * `-1`: Unable to open the file (missing, unreadable, or empty).
  * `0`: Video is fine and C2PA manifest/hash is validated.
  * `1`: No C2PA header found, header could not be confirmed, or hash mismatch.

* **`extract_c2pa(file_path: str) -> Optional[bytes]`**
  Extracts raw C2PA manifest/superbox bytes directly from container boxes. Returns `None` if not found.

* **`validate_with_c2patool(file_path: str) -> bool`**
  Validates manifest assertions and cryptographic hashes via `c2patool` (if installed) or `c2pa.Reader`. Returns `True` if valid.

### Standalone CLI
```bash
python3 c2pa2_checker.py video.mp4
# Returns and exits with: -1, 0, or 1
```

---

## 3. Logo Detector (`logo_detector.py`)

Detects persistent static and semi-transparent logos across sampled frames using temporal variance and spatial edge persistence.

### Core Class

* **`LogoDetector(max_samples=80, confidence_threshold=0.35)`**
  * `detect_in_video(video_path: str, output_annotated_frame: Optional[str] = None) -> dict`
    Samples video frames, locates stationary regions in candidate corners, and returns detected bounding boxes and confidence scores.

### Usage
```python
from logo_detector import LogoDetector

detector = LogoDetector(max_samples=80)
res = detector.detect_in_video("video.mp4", output_annotated_frame="annotated.jpg")

if res["detected"]:
    print(f"Found {res['watermark_count']} logo(s)")
```