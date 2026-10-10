import os
import pprint
import sys

# Ensure current directory is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from detector import detect

# Video directory (checks CLI arg, binary/videos, or local/binary/videos)
VIDEO_DIR = sys.argv[1] if len(sys.argv) > 1 else "binary/videos"
if not os.path.isdir(VIDEO_DIR):
    local_fallback = os.path.join(os.path.dirname(__file__), "videos")
    if os.path.isdir(local_fallback):
        VIDEO_DIR = local_fallback

if not os.path.exists(VIDEO_DIR):
    print(f"Directory not found: {VIDEO_DIR}")
    sys.exit(1)

# Collect all video files
extensions = (".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v")
video_files = sorted([
    os.path.join(VIDEO_DIR, f)
    for f in os.listdir(VIDEO_DIR)
    if f.lower().endswith(extensions)
])

if not video_files:
    print(f"No video files found in {VIDEO_DIR}")
    sys.exit(0)

print(f"Testing {len(video_files)} video(s) in '{VIDEO_DIR}':\n")
for video_path in video_files:
    print(f"=== {video_path} ===")
    result = detect(video_path)
    pprint.pprint(result)
    print()
