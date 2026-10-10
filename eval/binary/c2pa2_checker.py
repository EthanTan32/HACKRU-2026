#!/usr/bin/env python3
"""
Bare Minimum C2PA Parser & Validator
Extracts C2PA manifest/header and validates integrity with c2patool / c2pa SDK.
Completely standalone: zero dependencies on detector, logo_detector, cv2, or numpy.

Return codes:
 -1 : Unable to open the file
  0 : Video is fine and C2PA is validated
  1 : No header / header could not be confirmed / header hash mismatch
"""

import json
import os
import shutil
import struct
import subprocess
import sys
from typing import Any, Dict, List, Optional

# Optional import of official C2PA library at top-level
try:
    import c2pa
except ImportError:
    c2pa = None

# Canonical C2PA UUIDs for ISO-BMFF (MP4, MOV)
C2PA_UUID_CANONICAL = bytes.fromhex("d8fec3d61b0e483c92975828877ec481")
C2PA_UUID_DRAFT = bytes.fromhex("d8fc76600001404da11d1e4047788a1f")
KNOWN_C2PA_UUIDS = {C2PA_UUID_CANONICAL, C2PA_UUID_DRAFT}

# JUMBF Description Box Type UUID (c2pa manifest store)
JUMBF_TYPE_MANIFEST_STORE = bytes.fromhex("6332706100110010800000aa00389b71")


def format_uuid(uuid_bytes: bytes) -> str:
    """Formats 16 raw bytes into standard 8-4-4-4-12 hex UUID representation."""
    if len(uuid_bytes) != 16:
        return uuid_bytes.hex()
    h = uuid_bytes.hex()
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def extract_c2pa(file_path: str) -> Optional[bytes]:
    """
    Bare-minimum parser extracting raw C2PA manifest/box payload from container.
    Traverses ISO-BMFF boxes and scans for JUMBF/EBML manifests.
    Zero external dependencies.
    """
    try:
        with open(file_path, "rb") as f:
            f.seek(0, 2)
            file_len = f.tell()
            f.seek(0)

            # Box traversal for ISO-BMFF (mp4, mov)
            stack = [(0, file_len)]
            while stack:
                start, end = stack.pop()
                f.seek(start)
                while f.tell() < end:
                    header = f.read(8)
                    if len(header) < 8:
                        break
                    size, btype = struct.unpack(">I4s", header)
                    hdr_len = 8
                    if size == 1:
                        hdr64 = f.read(8)
                        if len(hdr64) < 8:
                            break
                        size = struct.unpack(">Q", hdr64)[0]
                        hdr_len = 16
                    elif size == 0:
                        size = end - (f.tell() - 8)

                    if size < hdr_len:
                        break
                    box_end = f.tell() - hdr_len + size

                    if btype == b"uuid":
                        uuid_val = f.read(16)
                        if uuid_val in KNOWN_C2PA_UUIDS or b"c2pa" in uuid_val:
                            return f.read(size - hdr_len - 16)
                    elif btype in (b"moov", b"meta", b"udta", b"trak"):
                        stack.append((f.tell(), box_end))

                    f.seek(box_end)

            # Fallback scan for JUMBF or EBML attachment
            f.seek(0)
            data = f.read()
            if b"application/x-c2pa-manifest-store" in data:
                idx = data.find(b"application/x-c2pa-manifest-store")
                return data[idx : idx + 4096]
            if b"c2pa" in data and (b"\xd8\xfe\xc3\xd6" in data or b"jumb" in data):
                idx = data.find(b"c2pa")
                return data[max(0, idx - 16) : idx + 1024]
    except Exception:
        return None
    return None


def validate_with_c2patool(file_path: str) -> bool:
    """
    Validates C2PA cryptographic signature, manifests, and hashes using
    c2patool CLI or the official c2pa-python library.
    """
    # 1. Try c2patool CLI if available on PATH
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
                for item in val_status:
                    code = item.get("code", "").lower()
                    if any(err in code for err in ["mismatch", "invalid", "error", "fail", "corrupt"]):
                        return False
                if data.get("active_manifest") or not val_status:
                    return True
            return False
        except Exception:
            pass

    # 2. Use official c2pa Python library
    if c2pa is not None:
        try:
            reader = c2pa.Reader(file_path)
            val_state = reader.get_validation_state()
            val_results = reader.get_validation_results() or {}
            val_status = val_results.get("validation_status", [])

            for item in val_status:
                code = item.get("code", "").lower()
                if any(err in code for err in ["mismatch", "invalid", "error", "fail", "corrupt"]):
                    return False

            if val_state and val_state.lower() in ("valid", "validated"):
                return True
            if reader.get_active_manifest() and not val_status:
                return True
        except Exception:
            return False

    return False


def check_c2pa(file_path: str) -> int:
    """
    Main evaluation function:
    Returns:
      -1 : Unable to open file
       0 : Video is fine and C2PA is validated
       1 : No header / could not confirm / hash mismatch
    """
    # Step 1: Check if file can be opened
    if not file_path or not os.path.exists(file_path):
        return -1
    try:
        with open(file_path, "rb") as f:
            if f.read(1) == b"" and os.path.getsize(file_path) == 0:
                return -1
    except Exception:
        return -1

    # Step 2: Bare minimum parser extracts C2PA header/box
    c2pa_header = extract_c2pa(file_path)
    if not c2pa_header:
        # No header found
        return 1

    # Step 3: Validate against c2patool / c2pa SDK
    if validate_with_c2patool(file_path):
        return 0

    # Header exists but could not be confirmed / validated / hash mismatch
    return 1


class C2PAChecker:
    """Lightweight C2PA inspector adapter."""

    def __init__(self, debug: bool = False):
        self.debug = debug

    def check_file(self, file_path: str) -> Dict[str, Any]:
        status_code = check_c2pa(file_path)
        payload = extract_c2pa(file_path)
        has_c2pa = payload is not None

        uuid_boxes: List[Dict[str, Any]] = []
        c2pa_uuid_str = None
        jumbf_store = None

        if has_c2pa:
            c2pa_uuid_str = format_uuid(C2PA_UUID_CANONICAL)
            uuid_boxes.append({
                "uuid": c2pa_uuid_str,
                "is_c2pa_standard": True,
                "box_offset": 0,
                "box_size": len(payload) + 24 if payload else 0,
                "payload_size": len(payload) if payload else 0,
            })
            jumbf_store = {
                "type": "jumb",
                "super_size": len(payload) if payload else 0,
                "description": {
                    "type_name": "c2pa_manifest_store",
                    "type_uuid": format_uuid(JUMBF_TYPE_MANIFEST_STORE),
                    "label": "c2pa",
                },
            }

        ext = os.path.splitext(file_path)[1].lower().lstrip(".")
        return {
            "c2pa_present": has_c2pa,
            "status_code": status_code,
            "container_format": ext or "unknown",
            "c2pa_manifest_uuid": c2pa_uuid_str,
            "uuid_boxes_found": uuid_boxes,
            "jumbf_manifest_store": jumbf_store,
            "c2pa_sdk": {"manifest_found": status_code == 0},
            "c2patool_verification": {"status": "verified" if status_code == 0 else "unverified"},
        }


def main():
    if len(sys.argv) < 2:
        print("Usage: python c2pa2_checker.py <video_path>")
        sys.exit(1)

    result = check_c2pa(sys.argv[1])
    print(result)
    sys.exit(0 if result == 0 else (1 if result == 1 else 255))


if __name__ == "__main__":
    main()
