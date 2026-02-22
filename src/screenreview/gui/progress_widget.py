# -*- coding: utf-8 -*-
"""Progress display for background tasks."""

from __future__ import annotations

from PyQt6.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget


class ProgressWidget(QWidget):
    """Display current pipeline step progress."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.title_label = QLabel("Progress")
        self.title_label.setObjectName("sectionTitle")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.status_label = QLabel("Idle")
        self.status_label.setObjectName("mutedText")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.title_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_label)

    def set_progress(self, step: int, total_steps: int, message: str) -> None:
        total_steps = max(1, int(total_steps))
        step = max(0, int(step))
        percent = int((step / total_steps) * 100)
        self.progress_bar.setValue(percent)
        self.status_label.setText(message)

