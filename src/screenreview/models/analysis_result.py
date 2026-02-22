# -*- coding: utf-8 -*-
"""Analysis result data model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from screenreview.models.screen_item import ScreenItem


@dataclass
class AnalysisResult:
    """Structured result produced by the multimodal analyzer."""

    screen: ScreenItem
    bugs: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    raw_response: str = ""
    model_used: str = ""
    cost_euro: float = 0.0

