# -*- coding: utf-8 -*-
"""Application state container for phase 1."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from screenreview.models.screen_item import ScreenItem


@dataclass
class AppState:
    """Mutable app state shared by GUI components."""

    project_dir: Path | None = None
    screens: list[ScreenItem] = field(default_factory=list)
    current_index: int = 0
    recording_active: bool = False
    settings: dict[str, Any] = field(default_factory=dict)

