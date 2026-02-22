# -*- coding: utf-8 -*-
"""Preflight check dialog for startup readiness validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from screenreview.core.precheck import Precheck, analyze_missing_screen_files, format_missing_file_report
from screenreview.integrations.openai_client import OpenAIClient
from screenreview.integrations.openrouter_client import OpenRouterClient
from screenreview.integrations.replicate_client import ReplicateClient


def build_preflight_report(project_dir: Path, settings: dict[str, Any]) -> dict[str, Any]:
    """Build a combined preflight report with local and remote checks."""
    openai_key = str(settings.get("api_keys", {}).get("openai", "")).strip()
    replicate_key = str(settings.get("api_keys", {}).get("replicate", "")).strip()
    openrouter_key = str(settings.get("api_keys", {}).get("openrouter", "")).strip()

    openai_client = OpenAIClient(api_key=openai_key)
    replicate_client = ReplicateClient(api_key=replicate_key)
    openrouter_client = OpenRouterClient(api_key=openrouter_key)

    precheck = Precheck(
        openai_validate=lambda key: openai_client.validate_key(key, check_remote=True, timeout=3.0),
        replicate_validate=lambda key: replicate_client.validate_key(key, check_remote=True, timeout=3.0),
        openrouter_validate=lambda key: openrouter_client.validate_key(key, check_remote=True, timeout=3.0),
    )
    base_checks = precheck.run(project_dir, settings)
    file_report = analyze_missing_screen_files(
        project_dir,
        viewport_mode=str(settings.get("viewport", {}).get("mode", "mobile")),
    )

    api_status = {
        "openai": {
            "valid": openai_client.validate_key(check_remote=True, timeout=3.0) if openai_key else False,
            "present": bool(openai_key),
        },
        "replicate": {
            "valid": replicate_client.validate_key(check_remote=True, timeout=3.0) if replicate_key else False,
            "present": bool(replicate_key),
        },
        "openrouter": {
            "valid": openrouter_client.validate_key(check_remote=True, timeout=3.0) if openrouter_key else False,
            "present": bool(openrouter_key),
        },
    }

    model_status: dict[str, Any] = {
        "openai": (
            openai_client.check_model_availability(
                model_ids=["gpt-4o-transcribe", "gpt-4o"],
                timeout=3.0,
            )
            if api_status["openai"]["valid"]
            else {}
        ),
        "replicate": (
            replicate_client.check_model_availability(
                model_aliases=["llama_32_vision", "qwen_vl"],
                timeout=3.0,
            )
            if api_status["replicate"]["valid"]
            else {}
        ),
        "openrouter": (
            openrouter_client.check_model_availability(
                model_aliases=["llama_32_vision", "qwen_vl", "gpt4o_vision"],
                timeout=3.0,
            )
            if api_status["openrouter"]["valid"]
            else {}
        ),
    }

    files_ok = int(file_report.get("missing_count", 0)) == 0
    critical_failures = [
        check for check in base_checks if check.get("check") != "cost_estimation" and not check.get("passed", False)
    ]
    ready = files_ok and not critical_failures
    return {
        "project_dir": str(project_dir),
        "base_checks": base_checks,
        "file_report": file_report,
        "api_status": api_status,
        "model_status": model_status,
        "ready": ready,
    }


class PreflightDialog(QDialog):
    """Display consolidated startup readiness information."""

    def __init__(self, project_dir: Path, settings: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project_dir = Path(project_dir)
        self.settings = settings
        self.setWindowTitle("Preflight Check")
        self.resize(860, 620)

        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        self.summary_label.setObjectName("sectionTitle")

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Check", "Status", "Message"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)

        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)

        self.refresh_button = QPushButton("Run Preflight Again")
        self.refresh_button.clicked.connect(self.refresh_report)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        buttons.button(QDialogButtonBox.StandardButton.Close).clicked.connect(self.reject)

        button_row = QHBoxLayout()
        button_row.addWidget(self.refresh_button)
        button_row.addStretch(1)
        button_row.addWidget(buttons)

        layout = QVBoxLayout(self)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.table, 2)
        layout.addWidget(self.detail_text, 2)
        layout.addLayout(button_row)

        self.refresh_report()

    def refresh_report(self) -> None:
        """Re-run all checks and refresh the dialog UI."""
        try:
            report = build_preflight_report(self.project_dir, self.settings)
        except Exception as exc:
            QMessageBox.critical(self, "Preflight Check Failed", f"Could not run preflight checks:\n{exc}")
            return

        self._render_report(report)

    def _render_report(self, report: dict[str, Any]) -> None:
        base_checks = list(report.get("base_checks", []))
        file_report = dict(report.get("file_report", {}))
        api_status = dict(report.get("api_status", {}))
        model_status = dict(report.get("model_status", {}))
        ready = bool(report.get("ready", False))

        files_ok = int(file_report.get("missing_count", 0)) == 0
        icon_ready = "OK" if ready else "ATTN"
        files_text = "OK" if files_ok else f"{file_report.get('missing_count', 0)} missing"
        self.summary_label.setText(
            "Preflight Summary | "
            f"Ready: {icon_ready} | Files: {files_text} | "
            f"OpenAI: {self._api_state_text(api_status.get('openai', {}))} | "
            f"Replicate: {self._api_state_text(api_status.get('replicate', {}))} | "
            f"OpenRouter: {self._api_state_text(api_status.get('openrouter', {}))}"
        )

        self.table.setRowCount(len(base_checks))
        for row, item in enumerate(base_checks):
            check_name = str(item.get("check", ""))
            passed = bool(item.get("passed", False))
            status_text = "OK" if passed else "FAIL"
            message = str(item.get("message", ""))
            self.table.setItem(row, 0, QTableWidgetItem(check_name))
            status_item = QTableWidgetItem(status_text)
            if passed:
                status_item.setForeground(Qt.GlobalColor.darkGreen)
            else:
                status_item.setForeground(Qt.GlobalColor.darkRed)
            self.table.setItem(row, 1, status_item)
            self.table.setItem(row, 2, QTableWidgetItem(message))
        self.table.resizeColumnsToContents()

        detail_lines = [
            "== File Report ==",
            format_missing_file_report(file_report),
            "",
            "== Model Availability ==",
            self._format_model_block("OpenAI", model_status.get("openai", {})),
            self._format_model_block("Replicate", model_status.get("replicate", {})),
            self._format_model_block("OpenRouter", model_status.get("openrouter", {})),
        ]
        self.detail_text.setPlainText("\n".join(detail_lines))

    def _api_state_text(self, data: dict[str, Any]) -> str:
        present = bool(data.get("present"))
        valid = bool(data.get("valid"))
        if not present:
            return "missing"
        return "ok" if valid else "error"

    def _format_model_block(self, title: str, models: dict[str, Any]) -> str:
        if not models:
            return f"{title}: skipped"
        lines = [f"{title}:"]
        for alias, result in models.items():
            if not isinstance(result, dict):
                continue
            lines.append(
                f"- {alias}: {'OK' if bool(result.get('ok')) else 'FAIL'} "
                f"(status={result.get('status')})"
            )
        return "\n".join(lines)
