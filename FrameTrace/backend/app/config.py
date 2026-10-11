import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STORAGE_DIR = Path(os.environ.get('FORENSICS_STORAGE_DIR', str(ROOT / 'data'))).resolve()
UPLOAD_DIR = STORAGE_DIR / 'uploads'
DB_PATH = STORAGE_DIR / 'jobs.sqlite3'
MAX_UPLOAD_BYTES = 100 * 1024 * 1024
MAX_DURATION_SECONDS = 30
SAMPLE_FPS = float(os.getenv('SAMPLE_FPS', '8'))
MAX_FRAMES = int(os.getenv('MAX_FRAMES', '240'))
FRAME_WIDTH = int(os.getenv('FRAME_WIDTH', '640'))
ENABLE_OCR = os.getenv('ENABLE_OCR', '0') == '1'
ENABLE_DEPTH = os.getenv('ENABLE_DEPTH', '0') == '1'
DEPTH_MODEL = os.getenv('DEPTH_MODEL', 'depth-anything/Depth-Anything-V2-Small-hf')
