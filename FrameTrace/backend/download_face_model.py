"""Download and verify the official MediaPipe Face Landmarker checkpoint."""
import argparse
import hashlib
import os
from pathlib import Path
import tempfile
from urllib.request import urlopen

URL = 'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task'
SHA256 = '64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff'


def download(output):
    output = Path(output).resolve()
    if output.exists():
        if hashlib.sha256(output.read_bytes()).hexdigest() != SHA256:
            raise ValueError('Existing file has a different checksum; choose another --output path')
        print('Verified existing model:', output)
        return output
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        digest = hashlib.sha256()
        with tempfile.NamedTemporaryFile(dir=output.parent, suffix='.download', delete=False) as target:
            temporary = Path(target.name)
            with urlopen(URL, timeout=120) as source:
                while chunk := source.read(1024 * 1024):
                    target.write(chunk)
                    digest.update(chunk)
        if digest.hexdigest() != SHA256:
            raise ValueError('Downloaded model checksum mismatch')
        if output.exists():
            raise ValueError('Output appeared during download; existing file preserved')
        os.replace(temporary, output)
        temporary = None
        print('Downloaded and verified model:', output)
        return output
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path,
                        default=Path(__file__).resolve().parent / 'data/models/face_landmarker.task')
    args = parser.parse_args()
    download(args.output)
