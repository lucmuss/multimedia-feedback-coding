# -*- coding: utf-8 -*-
"""Widget showing frame selection savings."""

from __future__ import annotations

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class SmartHintWidget(QWidget):
    """Display smart selector reduction metrics."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.title_label = QLabel("Smart Selector")
        self.title_label.setObjectName("sectionTitle")
        self.frames_label = QLabel("Frames: 0 -> 0")
        self.frames_label.setObjectName("mutedText")
        self.savings_label = QLabel("Saved: EUR 0.00")
        self.savings_label.setObjectName("mutedText")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.title_label)
        layout.addWidget(self.frames_label)
        layout.addWidget(self.savings_label)
        layout.addStretch(1)

    def set_stats(self, total_frames: int, selected_frames: int, saved_euro: float) -> None:
        self.frames_label.setText(f"Frames: {total_frames} -> {selected_frames}")
        self.savings_label.setText(f"Saved: EUR {saved_euro:.3f}")

