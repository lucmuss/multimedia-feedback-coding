# -*- coding: utf-8 -*-
"""Navigation and recording controls."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QGridLayout, QPushButton, QWidget


class ControlsWidget(QWidget):
    """Buttons for phase 1 navigation and placeholder recording actions."""

    back_requested = pyqtSignal()
    skip_requested = pyqtSignal()
    record_requested = pyqtSignal()
    pause_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    next_requested = pyqtSignal()

    def __init__(self, hotkeys: dict[str, str] | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        hotkeys = hotkeys or {}
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.back_button = self._make_button("Back", hotkeys.get("back", ""), self.back_requested.emit)
        self.skip_button = self._make_button("Skip", hotkeys.get("skip", ""), self.skip_requested.emit)
        self.record_button = self._make_button(
            "Record", hotkeys.get("record", ""), self.record_requested.emit, primary=True
        )
        self.pause_button = self._make_button("Pause", hotkeys.get("pause", ""), self.pause_requested.emit)
        self.stop_button = self._make_button("Stop", hotkeys.get("stop", ""), self.stop_requested.emit)
        self.next_button = self._make_button("Next", hotkeys.get("next", ""), self.next_requested.emit)

        for column, button in enumerate(
            [
                self.back_button,
                self.skip_button,
                self.record_button,
                self.pause_button,
                self.stop_button,
                self.next_button,
            ]
        ):
            layout.addWidget(button, 0, column)

    def _make_button(self, text: str, hotkey: str, handler, primary: bool = False) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("primaryButton" if primary else "secondaryButton")
        if hotkey:
            button.setToolTip(f"Shortcut: {hotkey}")
        button.clicked.connect(handler)
        return button

    def set_navigation_state(self, can_go_back: bool, can_go_next: bool) -> None:
        """Enable or disable navigation buttons."""
        self.back_button.setEnabled(can_go_back)
        self.next_button.setEnabled(can_go_next)

    def set_recording_state(self, is_recording: bool, is_paused: bool) -> None:
        """Update recording-related control states."""
        self.record_button.setText("Recording..." if is_recording and not is_paused else "Record")
        self.pause_button.setEnabled(is_recording)
        self.stop_button.setEnabled(is_recording)
        self.pause_button.setText("Resume" if is_paused else "Pause")
