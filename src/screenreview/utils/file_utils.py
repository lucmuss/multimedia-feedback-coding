# -*- coding: utf-8 -*-
"""File helpers with UTF-8 defaults."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def ensure_dir(path: str | Path) -> Path:
    """Create a directory if it does not exist."""
    dir_path = Path(path)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def read_json_file(path: str | Path) -> dict[str, Any]:
    """Read a JSON file."""
    file_path = Path(path)
    with file_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {file_path}")
    return data


def write_json_file(path: str | Path, data: dict[str, Any]) -> Path:
    """Write JSON to a file with indentation."""
    file_path = Path(path)
    ensure_dir(file_path.parent)
    with file_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=True)
        handle.write("\n")
    return file_path


def read_text_file(path: str | Path) -> str:
    """Read a UTF-8 text file."""
    file_path = Path(path)
    return file_path.read_text(encoding="utf-8")


def write_text_file(path: str | Path, content: str) -> Path:
    """Write a UTF-8 text file."""
    file_path = Path(path)
    ensure_dir(file_path.parent)
    file_path.write_text(content, encoding="utf-8")
    return file_path

