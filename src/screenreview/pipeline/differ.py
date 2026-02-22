# -*- coding: utf-8 -*-
"""Screenshot differ with byte-level fallback implementation."""

from __future__ import annotations

from pathlib import Path


DIFF_MARKER = b"SCREENREVIEW_DIFF_IMAGE"


class Differ:
    """Compute and persist a simple byte-level diff percentage."""

    def compute_diff(self, image_a: Path, image_b: Path) -> tuple[bytes, float]:
        data_a = image_a.read_bytes()
        data_b = image_b.read_bytes()
        max_len = max(len(data_a), len(data_b), 1)
        mismatches = sum(1 for a, b in zip(data_a, data_b) if a != b) + abs(len(data_a) - len(data_b))
        change_ratio = mismatches / max_len
        payload = DIFF_MARKER + b":" + str(round(change_ratio, 6)).encode("ascii")
        return payload, change_ratio

    def save_diff(self, diff_image: bytes, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(diff_image)

    def has_changed(self, image_a: Path, image_b: Path, threshold: float = 0.01) -> bool:
        _, ratio = self.compute_diff(image_a, image_b)
        return ratio > threshold

