# -*- coding: utf-8 -*-
"""Live transcript panel used during recording."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QTextEdit, QVBoxLayout, QWidget


class TranscriptLiveWidget(QWidget):
    """Display live transcript lines and simple trigger highlighting."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # title_label removed as per user request

        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setObjectName("transcriptLive")
        self.text_edit.setMaximumHeight(60) # Reduced height as requested

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0) # Minimal spacing
        layout.addWidget(self.text_edit, 1)

    def clear_transcript(self) -> None:
        self.text_edit.clear()
        # self.hint_label.setText("Waiting for recording...")  # Removed as per user request

    def append_segment(self, timestamp: float, text: str, event_type: str | None = None) -> None:
        label = f"[{int(timestamp // 60):02d}:{int(timestamp % 60):02d}]"
        prefix = f"{label} "
        if event_type:
            prefix += f"[{event_type.upper()}] "
        self.text_edit.append(prefix + text)
        # self.hint_label.setText("Recording active")  # Removed as per user request
