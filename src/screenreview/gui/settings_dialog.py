# -*- coding: utf-8 -*-
"""Settings dialog with tabs for phase 1 configuration."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QObject, QThread, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from screenreview.integrations.openai_client import OpenAIClient
from screenreview.integrations.openrouter_client import OpenRouterClient
from screenreview.integrations.replicate_client import ReplicateClient
from screenreview.gui.preflight_dialog import PreflightDialog


def _compute_api_validation_result(
    openai_key: str,
    replicate_key: str,
    openrouter_key: str,
) -> dict[str, Any]:
    """Run API and model checks and return UI-ready status payload."""
    openai_client = OpenAIClient()
    replicate_client = ReplicateClient()
    openrouter_client = OpenRouterClient()

    openai_ok = False
    replicate_ok = False
    openrouter_ok = False
    model_lines: list[str] = []
    service_statuses: dict[str, dict[str, str]] = {}

    if not openai_key:
        service_statuses["openai_status"] = {"state": "warn", "text": "No OpenAI key entered"}
        model_lines.append("OpenAI models: key missing")
    elif not openai_client.validate_key(openai_key, check_remote=False):
        service_statuses["openai_status"] = {"state": "error", "text": "OpenAI key format invalid"}
        model_lines.append("OpenAI models: skipped (invalid key format)")
    else:
        openai_ok = openai_client.validate_key(openai_key, check_remote=True, timeout=2.0)
        if openai_ok:
            service_statuses["openai_status"] = {"state": "ok", "text": "Connection OK"}
            openai_models = openai_client.check_model_availability(
                api_key=openai_key,
                model_ids=["gpt-4o-transcribe", "gpt-4o"],
                timeout=2.0,
            )
            transcribe_ok = bool(openai_models.get("gpt-4o-transcribe", {}).get("ok"))
            gpt4o_ok = bool(openai_models.get("gpt-4o", {}).get("ok"))
            model_lines.append(
                "OpenAI: gpt-4o-transcribe="
                + ("OK" if transcribe_ok else "MISSING")
                + ", gpt-4o (for gpt4o_vision alias)="
                + ("OK" if gpt4o_ok else "MISSING")
            )
        else:
            service_statuses["openai_status"] = {
                "state": "error",
                "text": "Connection failed or key not accepted",
            }
            model_lines.append("OpenAI models: skipped (key check failed)")

    if not replicate_key:
        service_statuses["replicate_status"] = {"state": "warn", "text": "No Replicate key entered"}
        model_lines.append("Replicate models: key missing")
    elif not replicate_client.validate_key(replicate_key, check_remote=False):
        service_statuses["replicate_status"] = {"state": "error", "text": "Replicate key format invalid"}
        model_lines.append("Replicate models: skipped (invalid key format)")
    else:
        replicate_ok = replicate_client.validate_key(
            replicate_key,
            check_remote=True,
            timeout=2.0,
        )
        if replicate_ok:
            service_statuses["replicate_status"] = {"state": "ok", "text": "Connection OK"}
            rep_models = replicate_client.check_model_availability(
                api_key=replicate_key,
                model_aliases=["llama_32_vision", "qwen_vl"],
                timeout=2.0,
            )
            llama_ok = bool(rep_models.get("llama_32_vision", {}).get("ok"))
            qwen_ok = bool(rep_models.get("qwen_vl", {}).get("ok"))
            model_lines.append(
                "Replicate: llama_32_vision="
                + ("OK" if llama_ok else "MISSING")
                + ", qwen_vl="
                + ("OK" if qwen_ok else "MISSING")
            )
        else:
            service_statuses["replicate_status"] = {
                "state": "error",
                "text": "Connection failed or key not accepted",
            }
            model_lines.append("Replicate models: skipped (key check failed)")

    if not openrouter_key:
        service_statuses["openrouter_status"] = {"state": "warn", "text": "No OpenRouter key entered"}
        model_lines.append("OpenRouter models: key missing")
    elif not openrouter_client.validate_key(openrouter_key, check_remote=False):
        service_statuses["openrouter_status"] = {"state": "error", "text": "OpenRouter key format invalid"}
        model_lines.append("OpenRouter models: skipped (invalid key format)")
    else:
        openrouter_client.api_key = openrouter_key
        openrouter_ok = openrouter_client.validate_key(
            openrouter_key,
            check_remote=True,
            timeout=2.0,
        )
        if openrouter_ok:
            service_statuses["openrouter_status"] = {"state": "ok", "text": "Connection OK"}
            or_models = openrouter_client.check_model_availability(
                api_key=openrouter_key,
                model_aliases=["llama_32_vision", "qwen_vl", "gpt4o_vision"],
                timeout=2.0,
            )
            model_lines.append(
                "OpenRouter: llama_32_vision="
                + ("OK" if bool(or_models.get("llama_32_vision", {}).get("ok")) else "MISSING")
                + ", qwen_vl="
                + ("OK" if bool(or_models.get("qwen_vl", {}).get("ok")) else "MISSING")
                + ", gpt4o_vision="
                + ("OK" if bool(or_models.get("gpt4o_vision", {}).get("ok")) else "MISSING")
            )
        else:
            service_statuses["openrouter_status"] = {
                "state": "error",
                "text": "Connection failed or key not accepted",
            }
            model_lines.append("OpenRouter models: skipped (key check failed)")

    model_text = " | ".join(model_lines) if model_lines else "No keys"
    if openai_ok or replicate_ok or openrouter_ok:
        model_state = "ok" if all("OK" in line for line in model_lines if ":" in line) else "warn"
    else:
        model_state = "warn"

    return {
        "services": service_statuses,
        "model_status": {"state": model_state, "text": model_text},
    }


class _ApiValidationWorker(QObject):
    """Worker object for running network validations outside the GUI thread."""

    finished = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    def __init__(self, request_id: int, keys: dict[str, str]) -> None:
        super().__init__()
        self._request_id = int(request_id)
        self._keys = dict(keys)

    def run(self) -> None:
        try:
            result = _compute_api_validation_result(
                openai_key=self._keys.get("openai", ""),
                replicate_key=self._keys.get("replicate", ""),
                openrouter_key=self._keys.get("openrouter", ""),
            )
        except Exception as exc:  # pragma: no cover - defensive worker boundary
            self.failed.emit(self._request_id, str(exc))
            return
        self.finished.emit(self._request_id, result)


class SettingsDialog(QDialog):
    """Modal settings dialog covering all settings groups."""

    TAB_NAMES = [
        "Quick Start",
        "API Keys",
        "Webcam & Audio",
        "Viewport",
        "Speech-to-Text",
        "Frame Extraction",
        "Gesture & OCR",
        "AI Analysis",
        "Cost",
        "Hotkeys",
        "Export",
    ]

    def __init__(
        self,
        settings: dict[str, Any],
        parent: QWidget | None = None,
        project_dir: Path | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(780, 560)
        self._settings = deepcopy(settings)
        self._project_dir = Path(project_dir) if project_dir is not None else None
        self._fields: dict[str, QWidget] = {}
        self._api_status_widgets: dict[str, tuple[QLabel, QLabel]] = {}
        self._quick_summary_label: QLabel | None = None
        self._openai_client = OpenAIClient()
        self._openrouter_client = OpenRouterClient()
        self._replicate_client = ReplicateClient()
        self._api_validation_thread: QThread | None = None
        self._api_validation_worker: _ApiValidationWorker | None = None
        self._api_validation_request_seq = 0
        self._api_validation_pending: tuple[int, dict[str, str]] | None = None
        self._pending_api_report_mode: str | None = None
        self._api_validation_timer = QTimer(self)
        self._api_validation_timer.setSingleShot(True)
        self._api_validation_timer.setInterval(700)
        self._api_validation_timer.timeout.connect(self._validate_api_statuses)

        self.tab_widget = QTabWidget()
        for name in self.TAB_NAMES:
            self.tab_widget.addTab(self._create_tab(name), name)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Apply
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.button_box.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self._apply_into_state)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Simple", "Advanced"])
        self.mode_combo.setToolTip("Simple hides advanced tabs. Advanced shows all settings.")
        self.mode_combo.currentTextChanged.connect(self._apply_settings_mode)
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Settings Mode"))
        mode_row.addWidget(self.mode_combo)
        mode_row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addLayout(mode_row)
        layout.addWidget(self.tab_widget, 1)
        layout.addWidget(self.button_box)

        self._apply_field_tooltips()
        self._connect_api_key_live_checks()
        self._apply_settings_mode("Simple")
        self._schedule_api_validation()

    def get_settings(self) -> dict[str, Any]:
        """Return the updated settings."""
        return deepcopy(self._settings)

    def accept(self) -> None:  # type: ignore[override]
        self._apply_into_state()
        self._stop_api_validation_thread()
        super().accept()

    def reject(self) -> None:  # type: ignore[override]
        self._stop_api_validation_thread()
        super().reject()

    def _apply_into_state(self) -> None:
        self._sync_quick_start_into_fields()
        self._settings["api_keys"]["openai"] = self._line("api_openai").text()
        self._settings["api_keys"]["replicate"] = self._line("api_replicate").text()
        self._settings["api_keys"]["openrouter"] = self._line("api_openrouter").text()
        self._settings["viewport"]["mode"] = self._combo("viewport_mode").currentText()
        self._settings["webcam"]["camera_index"] = self._spin("camera_index").value()
        self._settings["webcam"]["microphone_index"] = self._spin("mic_index").value()
        self._settings["webcam"]["resolution"] = self._combo("webcam_resolution").currentText()
        self._settings["speech_to_text"]["provider"] = self._combo("stt_provider").currentText()
        self._settings["speech_to_text"]["language"] = self._line("stt_language").text()
        self._settings["frame_extraction"]["interval_seconds"] = self._spin("frame_interval").value()
        self._settings["frame_extraction"]["max_frames_per_screen"] = self._spin("frame_max").value()
        self._settings["smart_selector"]["enabled"] = self._check("smart_enabled").isChecked()
        self._settings["gesture_detection"]["enabled"] = self._check("gesture_enabled").isChecked()
        self._settings["gesture_detection"]["sensitivity"] = self._dspin("gesture_sensitivity").value()
        self._settings["ocr"]["enabled"] = self._check("ocr_enabled").isChecked()
        self._settings["analysis"]["model"] = self._combo("analysis_model").currentText()
        self._settings["analysis"]["provider"] = self._combo("analysis_provider").currentText()
        self._settings["cost"]["budget_limit_euro"] = self._dspin("budget_limit").value()
        self._settings["cost"]["warning_at_euro"] = self._dspin("budget_warning").value()
        self._settings["cost"]["auto_stop_at_limit"] = self._check("budget_autostop").isChecked()
        self._settings["export"]["auto_export_after_analysis"] = self._check("export_auto").isChecked()
        self._settings["export"]["format"] = self._combo("export_format").currentText()

        hotkeys_editor = self._plain("hotkeys_editor").toPlainText().strip().splitlines()
        for line in hotkeys_editor:
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            self._settings["hotkeys"][key.strip()] = value.strip()

    def _create_tab(self, name: str) -> QWidget:
        if name == "Quick Start":
            return self._build_quick_start_tab()
        if name == "API Keys":
            return self._build_api_tab()
        if name == "Webcam & Audio":
            return self._build_webcam_tab()
        if name == "Viewport":
            return self._build_viewport_tab()
        if name == "Speech-to-Text":
            return self._build_stt_tab()
        if name == "Frame Extraction":
            return self._build_frame_tab()
        if name == "Gesture & OCR":
            return self._build_gesture_ocr_tab()
        if name == "AI Analysis":
            return self._build_analysis_tab()
        if name == "Cost":
            return self._build_cost_tab()
        if name == "Hotkeys":
            return self._build_hotkeys_tab()
        if name == "Export":
            return self._build_export_tab()
        return QWidget()

    def _build_quick_start_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)

        title = QLabel("Quick Start")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        project_label = QLabel(
            str(self._project_dir) if self._project_dir is not None else "No project selected yet"
        )
        project_label.setWordWrap(True)
        project_label.setToolTip("Current project routes directory used for scanning and preflight checks.")
        layout.addWidget(QLabel("Project Folder"))
        layout.addWidget(project_label)

        quick_form = QFormLayout()
        quick_form.addRow(
            "Viewport",
            self._register_combo(
                "quick_viewport_mode",
                ["mobile", "desktop"],
                self._settings["viewport"]["mode"],
            ),
        )
        quick_form.addRow(
            "AI Provider",
            self._register_combo(
                "quick_analysis_provider",
                ["replicate", "openrouter"],
                str(self._settings["analysis"].get("provider", "replicate")),
            ),
        )
        quick_form.addRow(
            "AI Model",
            self._register_combo(
                "quick_analysis_model",
                ["llama_32_vision", "qwen_vl", "gpt4o_vision"],
                self._settings["analysis"]["model"],
            ),
        )
        layout.addLayout(quick_form)

        preset_row = QHBoxLayout()
        self._fields["quick_preset"] = QComboBox()
        self._combo("quick_preset").addItems(
            ["Balanced (Recommended)", "Fast & Cheap", "High Accuracy", "Local-Only"]
        )
        apply_preset_button = QPushButton("Apply Preset")
        apply_preset_button.setToolTip("Apply a preset configuration to common settings.")
        apply_preset_button.clicked.connect(self._apply_selected_preset)
        preset_row.addWidget(QLabel("Preset"))
        preset_row.addWidget(self._combo("quick_preset"), 1)
        preset_row.addWidget(apply_preset_button)
        layout.addLayout(preset_row)

        button_row = QHBoxLayout()
        test_conn_button = QPushButton("Test Connections")
        test_conn_button.clicked.connect(self._on_test_connections)
        test_models_button = QPushButton("Test Models")
        test_models_button.clicked.connect(self._on_test_models)
        preflight_button = QPushButton("Run Preflight Check")
        preflight_button.clicked.connect(self._on_run_preflight)
        button_row.addWidget(test_conn_button)
        button_row.addWidget(test_models_button)
        button_row.addWidget(preflight_button)
        layout.addLayout(button_row)

        self._quick_summary_label = QLabel("Quick start summary will appear here.")
        self._quick_summary_label.setWordWrap(True)
        self._quick_summary_label.setObjectName("mutedText")
        layout.addWidget(self._quick_summary_label)

        help_text = QLabel(
            "Recommended startup flow: enter API keys -> choose provider/model -> run preflight -> "
            "start review session."
        )
        help_text.setWordWrap(True)
        help_text.setObjectName("mutedText")
        layout.addWidget(help_text)
        layout.addStretch(1)
        return tab

    def _build_api_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.addRow("OpenAI Key", self._register_line("api_openai", self._settings["api_keys"]["openai"], True))
        form.addRow(
            "Replicate Key",
            self._register_line("api_replicate", self._settings["api_keys"]["replicate"], True),
        )
        form.addRow(
            "OpenRouter Key",
            self._register_line("api_openrouter", self._settings["api_keys"].get("openrouter", ""), True),
        )
        form.addRow("OpenAI Status", self._create_status_row("openai_status"))
        form.addRow("Replicate Status", self._create_status_row("replicate_status"))
        form.addRow("OpenRouter Status", self._create_status_row("openrouter_status"))
        form.addRow("Model Status", self._create_status_row("model_status"))
        action_row = QHBoxLayout()
        test_conn_button = QPushButton("Test Connections")
        test_conn_button.clicked.connect(self._on_test_connections)
        test_models_button = QPushButton("Test Models")
        test_models_button.clicked.connect(self._on_test_models)
        action_row.addWidget(test_conn_button)
        action_row.addWidget(test_models_button)
        action_row.addStretch(1)
        action_box = QWidget()
        action_box.setLayout(action_row)
        form.addRow("", action_box)
        hint = QLabel(
            "Status updates automatically after key edits (debounced). "
            "Network checks run in the background with short timeouts."
        )
        hint.setWordWrap(True)
        hint.setObjectName("mutedText")
        form.addRow("", hint)
        return tab

    def _build_webcam_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.addRow("Camera Index", self._register_spin("camera_index", self._settings["webcam"]["camera_index"], 0, 16))
        form.addRow("Microphone Index", self._register_spin("mic_index", self._settings["webcam"]["microphone_index"], 0, 32))
        form.addRow(
            "Resolution",
            self._register_combo("webcam_resolution", ["720p", "1080p", "4k"], self._settings["webcam"]["resolution"]),
        )
        return tab

    def _build_viewport_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.addRow(
            "Mode",
            self._register_combo("viewport_mode", ["mobile", "desktop"], self._settings["viewport"]["mode"]),
        )
        hint = QLabel("Only matching folders (mobile/desktop) are scanned in phase 1.")
        hint.setWordWrap(True)
        form.addRow("", hint)
        return tab

    def _build_stt_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.addRow(
            "Provider",
            self._register_combo(
                "stt_provider",
                ["openai_4o_transcribe", "whisper_replicate", "whisper_local"],
                self._settings["speech_to_text"]["provider"],
            ),
        )
        form.addRow("Language", self._register_line("stt_language", self._settings["speech_to_text"]["language"]))
        return tab

    def _build_frame_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.addRow("Interval (sec)", self._register_spin("frame_interval", self._settings["frame_extraction"]["interval_seconds"], 1, 3600))
        form.addRow("Max Frames", self._register_spin("frame_max", self._settings["frame_extraction"]["max_frames_per_screen"], 1, 500))
        form.addRow("Smart Selector", self._register_check("smart_enabled", self._settings["smart_selector"]["enabled"]))
        return tab

    def _build_gesture_ocr_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.addRow("Gesture Detection", self._register_check("gesture_enabled", self._settings["gesture_detection"]["enabled"]))
        form.addRow("OCR", self._register_check("ocr_enabled", self._settings["ocr"]["enabled"]))
        form.addRow(
            "Gesture Sensitivity",
            self._register_dspin("gesture_sensitivity", float(self._settings["gesture_detection"]["sensitivity"]), 0.0, 1.0, 0.05),
        )
        return tab

    def _build_analysis_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.addRow(
            "Provider",
            self._register_combo(
                "analysis_provider",
                ["replicate", "openrouter"],
                str(self._settings["analysis"].get("provider", "replicate")),
            ),
        )
        form.addRow(
            "Model",
            self._register_combo(
                "analysis_model",
                ["llama_32_vision", "qwen_vl", "gpt4o_vision"],
                self._settings["analysis"]["model"],
            ),
        )
        hint = QLabel("Choose OpenRouter while Replicate access is blocked (403).")
        hint.setObjectName("mutedText")
        hint.setWordWrap(True)
        form.addRow("", hint)
        return tab

    def _build_cost_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.addRow(
            "Budget Limit (EUR)",
            self._register_dspin("budget_limit", float(self._settings["cost"]["budget_limit_euro"]), 0.0, 1000.0, 0.1),
        )
        form.addRow(
            "Warning At (EUR)",
            self._register_dspin("budget_warning", float(self._settings["cost"]["warning_at_euro"]), 0.0, 1000.0, 0.1),
        )
        form.addRow("Auto Stop", self._register_check("budget_autostop", self._settings["cost"]["auto_stop_at_limit"]))
        return tab

    def _build_hotkeys_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(QLabel("One mapping per line: action: shortcut"))
        editor = QPlainTextEdit()
        editor.setPlainText("\n".join(f"{k}: {v}" for k, v in self._settings["hotkeys"].items()))
        editor.setTabChangesFocus(True)
        self._fields["hotkeys_editor"] = editor
        layout.addWidget(editor, 1)
        return tab

    def _build_export_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.addRow(
            "Format",
            self._register_combo("export_format", ["markdown", "json"], self._settings["export"]["format"]),
        )
        form.addRow(
            "Auto Export",
            self._register_check("export_auto", self._settings["export"]["auto_export_after_analysis"]),
        )
        return tab

    def _register_line(self, key: str, value: str, password: bool = False) -> QLineEdit:
        widget = QLineEdit()
        widget.setText(value)
        if password:
            widget.setEchoMode(QLineEdit.EchoMode.Password)
        self._fields[key] = widget
        return widget

    def _register_spin(self, key: str, value: int, minimum: int, maximum: int) -> QSpinBox:
        widget = QSpinBox()
        widget.setRange(minimum, maximum)
        widget.setValue(int(value))
        self._fields[key] = widget
        return widget

    def _register_dspin(
        self,
        key: str,
        value: float,
        minimum: float,
        maximum: float,
        step: float,
    ) -> QDoubleSpinBox:
        widget = QDoubleSpinBox()
        widget.setDecimals(2)
        widget.setRange(minimum, maximum)
        widget.setSingleStep(step)
        widget.setValue(float(value))
        self._fields[key] = widget
        return widget

    def _register_combo(self, key: str, options: list[str], value: str) -> QComboBox:
        widget = QComboBox()
        widget.addItems(options)
        index = max(0, widget.findText(value, Qt.MatchFlag.MatchExactly))
        widget.setCurrentIndex(index)
        self._fields[key] = widget
        return widget

    def _register_check(self, key: str, value: bool) -> QCheckBox:
        widget = QCheckBox()
        widget.setChecked(bool(value))
        self._fields[key] = widget
        return widget

    def _create_status_row(self, key: str) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        indicator = QLabel()
        indicator.setFixedSize(12, 12)
        indicator.setStyleSheet(
            "background: #cbd5e1; border: 1px solid #94a3b8; border-radius: 6px;"
        )
        text = QLabel("Not checked")
        text.setWordWrap(True)
        self._api_status_widgets[key] = (indicator, text)
        layout.addWidget(indicator)
        layout.addWidget(text, 1)
        return row

    def _connect_api_key_live_checks(self) -> None:
        self._line("api_openai").textChanged.connect(self._schedule_api_validation)
        self._line("api_replicate").textChanged.connect(self._schedule_api_validation)
        self._line("api_openrouter").textChanged.connect(self._schedule_api_validation)

    def _schedule_api_validation(self) -> None:
        self._set_api_validation_pending_status()
        self._update_quick_start_summary()
        self._api_validation_timer.start()

    def _set_api_validation_pending_status(self) -> None:
        self._set_status("openai_status", "checking", "Checking OpenAI key...")
        self._set_status("replicate_status", "checking", "Checking Replicate key...")
        self._set_status("openrouter_status", "checking", "Checking OpenRouter key...")
        self._set_status("model_status", "checking", "Checking model availability...")

    def _set_status(self, key: str, state: str, text: str) -> None:
        indicator, label = self._api_status_widgets[key]
        palette = {
            "ok": ("#16a34a", "#15803d"),
            "warn": ("#eab308", "#ca8a04"),
            "error": ("#ef4444", "#dc2626"),
            "checking": ("#3b82f6", "#2563eb"),
            "idle": ("#cbd5e1", "#94a3b8"),
        }
        fill, border = palette.get(state, palette["idle"])
        indicator.setStyleSheet(
            f"background: {fill}; border: 1px solid {border}; border-radius: 6px;"
        )
        label.setText(text)
        self._update_quick_start_summary()

    def _validate_api_statuses(self) -> None:
        self._api_validation_request_seq += 1
        request_id = self._api_validation_request_seq
        payload = {
            "openai": self._line("api_openai").text().strip(),
            "replicate": self._line("api_replicate").text().strip(),
            "openrouter": self._line("api_openrouter").text().strip(),
        }
        if self._api_validation_thread is not None and self._api_validation_thread.isRunning():
            self._api_validation_pending = (request_id, payload)
            return
        self._start_api_validation_worker(request_id, payload)

    def _start_api_validation_worker(self, request_id: int, payload: dict[str, str]) -> None:
        thread = QThread(self)
        worker = _ApiValidationWorker(request_id, payload)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.finished.connect(self._on_api_validation_worker_finished)
        worker.failed.connect(self._on_api_validation_worker_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._on_api_validation_thread_finished)

        self._api_validation_thread = thread
        self._api_validation_worker = worker
        thread.start()

    def _on_api_validation_worker_finished(self, request_id: int, result: object) -> None:
        if request_id != self._api_validation_request_seq:
            return
        if not isinstance(result, dict):
            return
        self._apply_api_validation_result(result)
        if self._pending_api_report_mode is not None:
            self._show_api_status_report(include_models=self._pending_api_report_mode == "models")
            self._pending_api_report_mode = None

    def _on_api_validation_worker_failed(self, request_id: int, error_text: str) -> None:
        if request_id != self._api_validation_request_seq:
            return
        self._set_status("openai_status", "warn", "Check failed")
        self._set_status("replicate_status", "warn", "Check failed")
        self._set_status("openrouter_status", "warn", "Check failed")
        self._set_status("model_status", "error", f"API validation error: {error_text}")
        self._pending_api_report_mode = None

    def _on_api_validation_thread_finished(self) -> None:
        self._api_validation_thread = None
        self._api_validation_worker = None
        pending = self._api_validation_pending
        self._api_validation_pending = None
        if pending is not None:
            request_id, payload = pending
            self._start_api_validation_worker(request_id, payload)

    def _apply_api_validation_result(self, result: dict[str, Any]) -> None:
        services = result.get("services", {})
        for key in ("openai_status", "replicate_status", "openrouter_status"):
            data = services.get(key, {})
            self._set_status(
                key,
                str(data.get("state", "idle")),
                str(data.get("text", "Not checked")),
            )
        model_data = result.get("model_status", {})
        self._set_status(
            "model_status",
            str(model_data.get("state", "idle")),
            str(model_data.get("text", "Not checked")),
        )

    def _stop_api_validation_thread(self) -> None:
        self._api_validation_timer.stop()
        thread = self._api_validation_thread
        if thread is None:
            return
        if thread.isRunning():
            # Worker network calls use short timeouts; wait briefly to avoid QThread destruction warnings.
            thread.wait(3500)

    def _apply_settings_mode(self, mode_text: str) -> None:
        simple_visible = {
            "Quick Start",
            "API Keys",
            "Webcam & Audio",
            "Viewport",
            "AI Analysis",
            "Cost",
            "Export",
        }
        is_advanced = mode_text == "Advanced"
        for index, name in enumerate(self.TAB_NAMES):
            visible = is_advanced or name in simple_visible
            if hasattr(self.tab_widget, "setTabVisible"):
                self.tab_widget.setTabVisible(index, visible)
            else:
                self.tab_widget.setTabEnabled(index, visible)
        if not is_advanced and self.tab_widget.tabText(self.tab_widget.currentIndex()) not in simple_visible:
            self.tab_widget.setCurrentIndex(0)

    def _apply_field_tooltips(self) -> None:
        tips = {
            "api_openai": "OpenAI API key for GPT-4o Transcribe and optional GPT-4o model checks.",
            "api_replicate": "Replicate API key for vision analysis models (currently optional fallback).",
            "api_openrouter": "OpenRouter API key for alternate vision models when Replicate is unavailable.",
            "camera_index": "Webcam device index. Use 0 for the default camera.",
            "mic_index": "Microphone input device index. Use 0 for the default microphone.",
            "webcam_resolution": "Capture resolution for webcam recording. Higher resolution uses more storage.",
            "viewport_mode": "Filters scanned route folders to mobile or desktop.",
            "stt_provider": "Speech-to-text provider for audio transcription.",
            "stt_language": "Language hint for transcription (for example de or en).",
            "frame_interval": "Lower values extract more frames and increase processing cost.",
            "frame_max": "Maximum frames kept per screen after extraction/selection.",
            "smart_enabled": "Smart Selector keeps fewer relevant frames to reduce API cost.",
            "gesture_enabled": "Enable local gesture detection for pointer/hand highlighting.",
            "ocr_enabled": "Enable local OCR to extract text from selected frames.",
            "gesture_sensitivity": "Higher sensitivity may detect more gestures but can add false positives.",
            "analysis_provider": "Vision analysis backend. OpenRouter is recommended while Replicate is blocked.",
            "analysis_model": "Model alias used for multimodal bug analysis.",
            "budget_limit": "Session budget cap in EUR.",
            "budget_warning": "Warn when total cost reaches this amount.",
            "budget_autostop": "Stop analysis automatically when the budget limit is reached.",
            "export_format": "Output format for exports written to the route folders.",
            "export_auto": "Automatically export analysis results after processing.",
            "quick_viewport_mode": "Quick Start shortcut for viewport mode.",
            "quick_analysis_provider": "Quick Start shortcut for analysis provider.",
            "quick_analysis_model": "Quick Start shortcut for analysis model.",
            "quick_preset": "Preset bundles common settings for faster setup.",
        }
        for key, text in tips.items():
            widget = self._fields.get(key)
            if widget is not None and hasattr(widget, "setToolTip"):
                widget.setToolTip(text)

    def _sync_quick_start_into_fields(self) -> None:
        if "quick_viewport_mode" in self._fields:
            self._combo("viewport_mode").setCurrentText(self._combo("quick_viewport_mode").currentText())
        if "quick_analysis_provider" in self._fields:
            self._combo("analysis_provider").setCurrentText(
                self._combo("quick_analysis_provider").currentText()
            )
        if "quick_analysis_model" in self._fields:
            self._combo("analysis_model").setCurrentText(self._combo("quick_analysis_model").currentText())

    def _sync_quick_start_from_fields(self) -> None:
        if "quick_viewport_mode" in self._fields:
            self._combo("quick_viewport_mode").setCurrentText(self._combo("viewport_mode").currentText())
        if "quick_analysis_provider" in self._fields:
            self._combo("quick_analysis_provider").setCurrentText(
                self._combo("analysis_provider").currentText()
            )
        if "quick_analysis_model" in self._fields:
            self._combo("quick_analysis_model").setCurrentText(self._combo("analysis_model").currentText())

    def _apply_selected_preset(self) -> None:
        preset = self._combo("quick_preset").currentText()
        if preset == "Fast & Cheap":
            self._combo("analysis_provider").setCurrentText("openrouter")
            self._combo("analysis_model").setCurrentText("qwen_vl")
            self._spin("frame_interval").setValue(7)
            self._spin("frame_max").setValue(5)
            self._check("smart_enabled").setChecked(True)
        elif preset == "High Accuracy":
            self._combo("analysis_provider").setCurrentText("openrouter")
            self._combo("analysis_model").setCurrentText("gpt4o_vision")
            self._spin("frame_interval").setValue(3)
            self._spin("frame_max").setValue(12)
            self._check("smart_enabled").setChecked(True)
        elif preset == "Local-Only":
            self._combo("stt_provider").setCurrentText("whisper_local")
            self._check("gesture_enabled").setChecked(True)
            self._check("ocr_enabled").setChecked(True)
        else:  # Balanced (Recommended)
            self._combo("analysis_provider").setCurrentText("openrouter")
            self._combo("analysis_model").setCurrentText("llama_32_vision")
            self._spin("frame_interval").setValue(5)
            self._spin("frame_max").setValue(8)
            self._check("smart_enabled").setChecked(True)
            self._combo("stt_provider").setCurrentText("openai_4o_transcribe")
        self._sync_quick_start_from_fields()
        self._update_quick_start_summary()

    def _on_test_connections(self) -> None:
        self._pending_api_report_mode = "connections"
        self._set_api_validation_pending_status()
        self._validate_api_statuses()

    def _on_test_models(self) -> None:
        self._pending_api_report_mode = "models"
        self._set_api_validation_pending_status()
        self._validate_api_statuses()

    def _on_run_preflight(self) -> None:
        self._apply_into_state()
        if self._project_dir is None:
            QMessageBox.information(
                self,
                "Preflight Check",
                "No project folder is loaded yet. Open a project in the main window first.",
            )
            return
        dialog = PreflightDialog(self._project_dir, self._settings, self)
        dialog.exec()

    def _show_api_status_report(self, include_models: bool) -> None:
        lines = [
            f"OpenAI: {self._api_status_widgets['openai_status'][1].text()}",
            f"Replicate: {self._api_status_widgets['replicate_status'][1].text()}",
            f"OpenRouter: {self._api_status_widgets['openrouter_status'][1].text()}",
        ]
        if include_models:
            lines.append("")
            lines.append("Model Status:")
            lines.append(self._api_status_widgets["model_status"][1].text())
        QMessageBox.information(self, "API Check Results", "\n".join(lines))

    def _update_quick_start_summary(self) -> None:
        if self._quick_summary_label is None:
            return
        project_text = str(self._project_dir) if self._project_dir is not None else "No project"
        provider = (
            self._combo("quick_analysis_provider").currentText()
            if "quick_analysis_provider" in self._fields
            else str(self._settings.get("analysis", {}).get("provider", "replicate"))
        )
        model = (
            self._combo("quick_analysis_model").currentText()
            if "quick_analysis_model" in self._fields
            else str(self._settings.get("analysis", {}).get("model", "llama_32_vision"))
        )
        openai_text = self._api_status_widgets.get("openai_status", (None, QLabel("")))[1].text()
        replicate_text = self._api_status_widgets.get("replicate_status", (None, QLabel("")))[1].text()
        openrouter_text = self._api_status_widgets.get("openrouter_status", (None, QLabel("")))[1].text()
        self._quick_summary_label.setText(
            "Project: "
            + project_text
            + "\nViewport: "
            + (
                self._combo("quick_viewport_mode").currentText()
                if "quick_viewport_mode" in self._fields
                else str(self._settings.get("viewport", {}).get("mode", "mobile"))
            )
            + f"\nAnalysis: {provider} / {model}"
            + f"\nOpenAI: {openai_text}"
            + f"\nReplicate: {replicate_text}"
            + f"\nOpenRouter: {openrouter_text}"
        )

    def _line(self, key: str) -> QLineEdit:
        return self._fields[key]  # type: ignore[return-value]

    def _spin(self, key: str) -> QSpinBox:
        return self._fields[key]  # type: ignore[return-value]

    def _dspin(self, key: str) -> QDoubleSpinBox:
        return self._fields[key]  # type: ignore[return-value]

    def _combo(self, key: str) -> QComboBox:
        return self._fields[key]  # type: ignore[return-value]

    def _check(self, key: str) -> QCheckBox:
        return self._fields[key]  # type: ignore[return-value]

    def _plain(self, key: str) -> QPlainTextEdit:
        return self._fields[key]  # type: ignore[return-value]
