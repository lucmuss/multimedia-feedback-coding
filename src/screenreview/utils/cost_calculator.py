# -*- coding: utf-8 -*-
"""Realtime cost tracking and estimation."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from screenreview.models.cost_entry import CostEntry


PRICES = {
    "openai_4o_transcribe": {"provider": "openai", "unit": "minute", "price_euro": 0.006},
    "whisper_replicate": {"provider": "replicate", "unit": "minute", "price_euro": 0.003},
    "whisper_local": {"provider": "local", "unit": "minute", "price_euro": 0.0},
    "llama_32_vision": {"provider": "replicate", "unit": "image", "price_euro": 0.002},
    "qwen_vl": {"provider": "replicate", "unit": "image", "price_euro": 0.001},
    "gpt4o_vision": {"provider": "openai", "unit": "image", "price_euro": 0.01},
    "openrouter:llama_32_vision": {"provider": "openrouter", "unit": "image", "price_euro": 0.002},
    "openrouter:qwen_vl": {"provider": "openrouter", "unit": "image", "price_euro": 0.001},
    "openrouter:gpt4o_vision": {"provider": "openrouter", "unit": "image", "price_euro": 0.01},
    "easyocr_local": {"provider": "local", "unit": "image", "price_euro": 0.0},
    "mediapipe_local": {"provider": "local", "unit": "frame", "price_euro": 0.0},
}


class CostCalculator:
    """Track cost entries and provide summaries."""

    def __init__(self) -> None:
        self._entries: list[CostEntry] = []

    def add(self, provider: str, units: float, screen_name: str) -> CostEntry:
        """Add a cost entry.

        `provider` is treated as a model key if present in `PRICES`, otherwise as a provider name with zero price.
        """
        model_key = str(provider)
        price_info = PRICES.get(model_key)
        if price_info is None:
            entry = CostEntry(
                provider=model_key,
                model=model_key,
                units=float(units),
                cost_euro=0.0,
                timestamp=datetime.now(timezone.utc),
                screen_name=screen_name,
            )
        else:
            cost = round(float(units) * float(price_info["price_euro"]), 6)
            entry = CostEntry(
                provider=str(price_info["provider"]),
                model=model_key,
                units=float(units),
                cost_euro=cost,
                timestamp=datetime.now(timezone.utc),
                screen_name=screen_name,
            )
        self._entries.append(entry)
        return entry

    def get_total(self) -> float:
        return round(sum(entry.cost_euro for entry in self._entries), 6)

    def get_breakdown(self) -> dict[str, float]:
        breakdown: dict[str, float] = defaultdict(float)
        for entry in self._entries:
            breakdown[entry.provider] += entry.cost_euro
        return {key: round(value, 6) for key, value in breakdown.items()}

    def get_screen_cost(self, screen_name: str) -> float:
        return round(sum(e.cost_euro for e in self._entries if e.screen_name == screen_name), 6)

    def estimate_remaining(self, screens_left: int) -> float:
        if screens_left <= 0:
            return 0.0
        priced_entries = [entry for entry in self._entries if entry.cost_euro > 0]
        if not priced_entries:
            return 0.0
        by_screen: dict[str, float] = defaultdict(float)
        for entry in priced_entries:
            by_screen[entry.screen_name] += entry.cost_euro
        avg_per_screen = sum(by_screen.values()) / max(1, len(by_screen))
        return round(avg_per_screen * int(screens_left), 6)

    def is_over_budget(self, budget: float) -> bool:
        return self.get_total() > float(budget)

    def is_near_budget(self, budget: float, warning_at: float) -> bool:
        total = self.get_total()
        return total >= float(warning_at) and total <= float(budget)

    def reset(self) -> None:
        self._entries.clear()

    @property
    def entries(self) -> list[CostEntry]:
        return list(self._entries)
