# -*- coding: utf-8 -*-
"""Image helper functions with stdlib-only fallbacks."""

from __future__ import annotations

import base64
from pathlib import Path


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def encode_file_base64(path: str | Path) -> str:
    """Encode a file as base64 text."""
    file_path = Path(path)
    return base64.b64encode(file_path.read_bytes()).decode("ascii")


def decode_base64_to_file(data: str, path: str | Path) -> Path:
    """Decode base64 text to a file."""
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(base64.b64decode(data.encode("ascii")))
    return file_path


def is_png_bytes(data: bytes) -> bool:
    """Return True if bytes look like a PNG file."""
    return data.startswith(PNG_SIGNATURE)


def load_image_bytes(path: str | Path) -> bytes:
    """Read image bytes from disk."""
    return Path(path).read_bytes()

