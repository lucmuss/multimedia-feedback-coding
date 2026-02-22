# -*- coding: utf-8 -*-
"""Live cost summary widget."""

from __future__ import annotations

from PyQt6.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget


class CostWidget(QWidget):
    """Display screen/session cost and budget usage."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.title_label = QLabel("Cost")
        self.title_label.setObjectName("sectionTitle")
        self.screen_cost_label = QLabel("Screen: EUR 0.000")
        self.screen_cost_label.setObjectName("mutedText")
        self.session_cost_label = QLabel("Session: EUR 0.000")
        self.session_cost_label.setObjectName("mutedText")
        self.budget_label = QLabel("Budget: -")
        self.budget_label.setObjectName("mutedText")
        self.budget_bar = QProgressBar()
        self.budget_bar.setRange(0, 100)
        self.budget_bar.setValue(0)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.title_label)
        layout.addWidget(self.screen_cost_label)
        layout.addWidget(self.session_cost_label)
        layout.addWidget(self.budget_label)
        layout.addWidget(self.budget_bar)

    def set_costs(self, screen_cost: float, session_cost: float, budget_limit: float | None) -> None:
        self.screen_cost_label.setText(f"Screen: EUR {screen_cost:.3f}")
        self.session_cost_label.setText(f"Session: EUR {session_cost:.3f}")
        if budget_limit is None or budget_limit <= 0:
            self.budget_label.setText("Budget: not set")
            self.budget_bar.setValue(0)
            return
        pct = max(0, min(100, int((session_cost / budget_limit) * 100)))
        self.budget_label.setText(f"Budget: EUR {session_cost:.3f} / {budget_limit:.3f}")
        self.budget_bar.setValue(pct)

