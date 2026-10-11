#!/usr/bin/env python3
"""
C2PA Checker

Return Codes:
 -1 : Unable to open the file
  0 : Video is fine and C2PA is validated
  1 : No header / header could not be confirmed / header hash mismatch
"""

import json
import os
import shutil
import subprocess
import sys
from typing import Any, Dict, Optional

# Official external C2PA library
try:
    import c2pa
except ImportError:
    c2pa = None


def extract_c2pa(file_path: str) -> Optional[Dict[str, Any]]:
    """
    Extracts C2PA manifest store using the external c2pa library.
    Returns parsed manifest dict, or None if no C2PA data is found.
    """
    if c2pa is None or not os.path.isfile(file_path):
        return None
    try:
        reader = c2pa.Reader.try_create(file_path)
        if reader is not None:
            raw_json = reader.json()
            return json.loads(raw_json) if raw_json else None
    except Exception:
        return None
    return None


def validate_with_c2patool(file_path: str) -> bool:
    """
    Validates C2PA cryptographic signature, manifest, and hash integrity
    using the external c2patool CLI or the official c2pa Python SDK.
    """
    # 1. External c2patool CLI (if installed on PATH)
    c2pa_bin = shutil.which("c2patool")
    if c2pa_bin:
        try:
            res = subprocess.run(
                [c2pa_bin, file_path, "--detailed"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if res.returncode == 0 and res.stdout.strip():
                data = json.loads(res.stdout)
                val_status = data.get("validation_status", [])
                active_manifest = data.get("active_manifest")
                if active_manifest:
                    has_error = any(
                        any(err in str(item.get("code", "")).lower() for err in ["mismatch", "invalid", "error", "fail", "corrupt", "untrusted"])
                        for item in val_status
                    )
                    if not has_error:
                        return True
            return False
        except Exception:
            pass

    # 2. External c2pa-python library
    if c2pa is not None:
        try:
            reader = c2pa.Reader(file_path)
            if hasattr(reader, "is_valid") and not reader.is_valid():
                return False

            val_state = reader.get_validation_state() if hasattr(reader, "get_validation_state") else None
            val_results = reader.get_validation_results() if hasattr(reader, "get_validation_results") else {}
            val_status = (val_results or {}).get("validation_status", [])

            has_error = any(
                any(err in str(item.get("code", "")).lower() for err in ["mismatch", "invalid", "error", "fail", "corrupt", "untrusted"])
                for item in val_status
            )
            if has_error:
                return False

            active_manifest = reader.get_active_manifest() if hasattr(reader, "get_active_manifest") else None
            if active_manifest and (val_state is None or str(val_state).lower() in ("valid", "validated")):
                return True
        except Exception:
            return False

    return False


def check_c2pa(file_path: str) -> int:
    """
    Main evaluation function using external c2pa libraries.

    Returns:
      -1 : Unable to open file
       0 : Video is fine and C2PA is validated
       1 : No header / could not confirm / hash mismatch
    """
    # Step 1: Check if file can be opened
    if not file_path or not os.path.isfile(file_path):
        return -1
    try:
        with open(file_path, "rb") as f:
            if f.read(1) == b"" and os.path.getsize(file_path) == 0:
                return -1
    except Exception:
        return -1

    # Step 2: Validate via c2patool CLI or c2pa Python library
    # c2patool / c2pa.Reader handles manifest extraction and hash verification
    if validate_with_c2patool(file_path):
        return 0

    # Step 3: Check if a manifest exists at all (if not validated)
    manifest = extract_c2pa(file_path)
    if manifest is None:
        return 1  # No C2PA header found

    # Header exists but could not be confirmed / signature or hash mismatch
    return 1

def main():
    if len(sys.argv) < 2:
        print("Usage: python c2pa2_checker.py <video_path>")
        sys.exit(1)

    result = check_c2pa(sys.argv[1])
    print(result)
    sys.exit(0 if result == 0 else (1 if result == 1 else 255))


if __name__ == "__main__":
    main()
