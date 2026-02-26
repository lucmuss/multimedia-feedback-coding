# -*- coding: utf-8 -*-
"""Screen item data model."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class ScreenItem:
    """Metadata and paths for a single screen review item."""

    name: str
    route: str
    viewport: str
    viewport_size: dict
    timestamp_utc: str
    git_branch: str
    git_commit: str
    browser: str
    screenshot_path: Path
    transcript_path: Path
    metadata_path: Path
    extraction_dir: Path
    status: str = "pending"
    error: str | None = None
