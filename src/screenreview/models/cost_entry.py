# -*- coding: utf-8 -*-
"""Cost tracking data model."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class CostEntry:
    """Single cost ledger entry."""

    provider: str
    model: str
    units: float
    cost_euro: float
    timestamp: datetime
    screen_name: str

