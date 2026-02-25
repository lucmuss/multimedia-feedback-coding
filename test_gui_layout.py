#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test GUI layout to verify button alignment."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel
from PyQt6.QtCore import Qt
from screenreview.gui.controls_widget import ControlsWidget


class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Button Layout Test")
        self.resize(1200, 300)
        
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)
        
        # Add label
        label = QLabel("Button Layout Test - Buttons should be left-aligned:")
        label.setObjectName("appTitle")
        layout.addWidget(label)
        
        # Add controls widget
        controls = ControlsWidget(hotkeys={})
        layout.addWidget(controls)
        
        # Add stretch at bottom
        layout.addStretch()
        
        self.setCentralWidget(central)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec())
