# -*- coding: utf-8 -*-
"""Live transcript panel used during recording."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QTextEdit, QVBoxLayout, QWidget


class TranscriptLiveWidget(QWidget):
    """Display live transcript lines and simple trigger highlighting."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.title_label = QLabel("Live Transcript")
        self.title_label.setObjectName("sectionTitle")

        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setObjectName("transcriptLive")
        self.text_edit.setMinimumHeight(72)

        self.hint_label = QLabel("Waiting for recording...")
        self.hint_label.setObjectName("mutedText")
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignLeft)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.title_label)
        layout.addWidget(self.text_edit, 1)
        layout.addWidget(self.hint_label)

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
