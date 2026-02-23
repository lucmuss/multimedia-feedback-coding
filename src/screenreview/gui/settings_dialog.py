# -*- coding: utf-8 -*-
"""Settings dialog with tabs for phase 1 configuration."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import tempfile
import time
from typing import Any

from PyQt6.QtCore import QObject, QThread, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
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
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTabBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from screenreview.integrations.openai_client import OpenAIClient
from screenreview.integrations.openrouter_client import OpenRouterClient
from screenreview.integrations.replicate_client import ReplicateClient
from screenreview.gui.help_system import HelpSystem
from screenreview.gui.preflight_dialog import PreflightDialog
from screenreview.pipeline.recorder import AudioLevelMonitor, CameraPreviewMonitor, Recorder

try:  # Optional runtime feature (device labels in webcam/audio tab)
    from PyQt6.QtMultimedia import QMediaDevices
except Exception:  # pragma: no cover - depends on local Qt multimedia runtime
    QMediaDevices = None  # type: ignore[assignment]


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

class _CameraResolutionWorker(QObject):
    """Worker object for running camera resolution probes without UI freeze."""
    finished = pyqtSignal(int, list, str)

    def __init__(self, camera_index: int) -> None:
        super().__init__()
        self._camera_index = camera_index

    def run(self) -> None:
        try:
            import logging
            logger = logging.getLogger("screenreview.gui.settings_dialog")
            logger.debug(f"[_CameraResolutionWorker] Probing camera index {self._camera_index}")
            from screenreview.pipeline.recorder import Recorder
            result = Recorder.probe_camera_resolution_options(self._camera_index)
            options = [str(v) for v in result.get("options", []) if str(v).strip()]
            if not options:
                options = ["720p", "1080p", "4k"]
            logger.debug(f"[_CameraResolutionWorker] Result options: {options}")
            self.finished.emit(self._camera_index, options, str(result.get("message", "")))
        except Exception as exc:
            self.finished.emit(self._camera_index, ["720p", "1080p", "4k"], f"Probe failed: {exc}")


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
        self._api_status_states: dict[str, str] = {}
        self._quick_summary_label: QLabel | None = None
        self._camera_name_label: QLabel | None = None
        self._mic_name_label: QLabel | None = None
        self._camera_device_combo: QComboBox | None = None
        self._mic_device_combo: QComboBox | None = None
        self._camera_preview_label: QLabel | None = None
        self._audio_feedback_label: QLabel | None = None
        self._audio_level_bar: QProgressBar | None = None
        self._camera_preview_pixmap: QPixmap | None = None
        self._resolution_info_label: QLabel | None = None
        self._camera_preview_monitor = CameraPreviewMonitor()
        self._audio_level_monitor = AudioLevelMonitor()
        self._camera_resolution_cache: dict[int, list[str]] = {}
        self._camera_resolution_probe_active = False
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
        self._device_feedback_timer = QTimer(self)
        self._device_feedback_timer.setSingleShot(True)
        self._device_feedback_timer.setInterval(1800)
        self._device_feedback_timer.timeout.connect(self._clear_device_feedback_hint)
        self._camera_probe_timer = QTimer(self)
        self._camera_probe_timer.setSingleShot(True)
        self._camera_probe_timer.setInterval(250)
        self._camera_probe_timer.timeout.connect(self._refresh_camera_preview_pipeline)
        
        self._camera_probe_thread: QThread | None = None
        self._camera_probe_worker: _CameraResolutionWorker | None = None

        self._audio_probe_timer = QTimer(self)
        self._audio_probe_timer.setSingleShot(True)
        self._audio_probe_timer.setInterval(250)
        self._audio_probe_timer.timeout.connect(self._restart_audio_monitor)
        self._device_monitor_ui_timer = QTimer(self)
        self._device_monitor_ui_timer.setInterval(120)
        self._device_monitor_ui_timer.timeout.connect(self._refresh_live_device_feedback)

        self.tab_widget = QTabWidget()
        for name in self.TAB_NAMES:
            self.tab_widget.addTab(self._create_tab(name), name)
        self._add_tab_help_buttons()
        self._apply_tab_tooltips()

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Apply
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.button_box.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self._apply_into_state)

        self.mode_combo = QComboBox()
        self.mode_combo.setObjectName("settingsModeCombo")
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
        self._refresh_analysis_provider_options()
        self._refresh_media_device_labels()
        self._apply_settings_mode("Simple")
        self._schedule_api_validation()

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        parent = self.parentWidget()
        if parent is not None:
            self.setGeometry(parent.geometry())
        self.raise_()
        self.activateWindow()
        self._camera_probe_timer.start()
        self._audio_probe_timer.start()
        if not self._device_monitor_ui_timer.isActive():
            self._device_monitor_ui_timer.start()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        if self._camera_preview_pixmap is None or self._camera_preview_label is None:
            return
        scaled = self._camera_preview_pixmap.scaled(
            self._camera_preview_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._camera_preview_label.setPixmap(scaled)

    def get_settings(self) -> dict[str, Any]:
        """Return the updated settings."""
        return deepcopy(self._settings)

    def accept(self) -> None:  # type: ignore[override]
        self._apply_into_state()
        self._stop_device_monitors()
        self._stop_api_validation_thread()
        super().accept()

    def reject(self) -> None:  # type: ignore[override]
        self._stop_device_monitors()
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
        self._settings["analysis"]["enabled"] = self._check("analysis_enabled").isChecked()
        model_text = self._combo("analysis_model").currentText().strip()
        provider_text = self._combo("analysis_provider").currentText().strip()
        if model_text:
            self._settings["analysis"]["model"] = model_text
        if provider_text:
            self._settings["analysis"]["provider"] = provider_text
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
        camera_index = self._register_spin("camera_index", self._settings["webcam"]["camera_index"], 0, 16)
        mic_index = self._register_spin("mic_index", self._settings["webcam"]["microphone_index"], 0, 32)
        camera_row = QWidget()
        camera_layout = QVBoxLayout(camera_row)
        camera_layout.setContentsMargins(0, 0, 0, 0)
        camera_layout.setSpacing(4)
        self._camera_device_combo = QComboBox()
        self._camera_device_combo.setToolTip(
            "Select a detected camera by name. The camera index field is updated automatically."
        )
        self._camera_name_label = QLabel("Detected device: loading...")
        self._camera_name_label.setWordWrap(True)
        self._camera_name_label.setObjectName("mutedText")
        camera_layout.addWidget(self._camera_device_combo)
        camera_layout.addWidget(camera_index)
        camera_layout.addWidget(self._camera_name_label)
        form.addRow("Camera Index", camera_row)

        mic_row = QWidget()
        mic_layout = QVBoxLayout(mic_row)
        mic_layout.setContentsMargins(0, 0, 0, 0)
        mic_layout.setSpacing(4)
        self._mic_device_combo = QComboBox()
        self._mic_device_combo.setToolTip(
            "Select a detected microphone by name. The microphone index field is updated automatically."
        )
        self._mic_name_label = QLabel("Detected device: loading...")
        self._mic_name_label.setWordWrap(True)
        self._mic_name_label.setObjectName("mutedText")
        mic_layout.addWidget(self._mic_device_combo)
        mic_layout.addWidget(mic_index)
        mic_layout.addWidget(self._mic_name_label)
        form.addRow("Microphone Index", mic_row)
        resolution_row = QWidget()
        resolution_layout = QVBoxLayout(resolution_row)
        resolution_layout.setContentsMargins(0, 0, 0, 0)
        resolution_layout.setSpacing(4)
        resolution_combo = self._register_combo(
            "webcam_resolution",
            ["720p", "1080p", "4k"],
            self._settings["webcam"]["resolution"],
        )
        self._resolution_info_label = QLabel("Resolution options will be detected for the selected camera.")
        self._resolution_info_label.setObjectName("mutedText")
        self._resolution_info_label.setWordWrap(True)
        resolution_layout.addWidget(resolution_combo)
        resolution_layout.addWidget(self._resolution_info_label)
        form.addRow("Resolution", resolution_row)
        test_row = QHBoxLayout()
        test_webcam_button = QPushButton("Test Webcam")
        test_webcam_button.setToolTip(
            "Check whether the selected camera can return a preview frame. "
            "Uses live capture when runtime dependencies/devices are available."
        )
        test_webcam_button.clicked.connect(self._on_test_webcam_device)
        test_audio_button = QPushButton("Test Audio")
        test_audio_button.setToolTip(
            "Check microphone device selection, sample audio level, and run a short recorder pipeline test."
        )
        test_audio_button.clicked.connect(self._on_test_audio_device)
        test_row.addWidget(test_webcam_button)
        test_row.addWidget(test_audio_button)
        test_row.addStretch(1)
        test_box = QWidget()
        test_box.setLayout(test_row)
        form.addRow("Diagnostics", test_box)
        if hasattr(camera_index, "valueChanged"):
            camera_index.valueChanged.connect(self._refresh_media_device_labels)
            camera_index.valueChanged.connect(self._sync_device_selectors_from_indices)
            camera_index.valueChanged.connect(lambda *_: self._camera_probe_timer.start())
        if hasattr(mic_index, "valueChanged"):
            mic_index.valueChanged.connect(self._refresh_media_device_labels)
            mic_index.valueChanged.connect(self._sync_device_selectors_from_indices)
            mic_index.valueChanged.connect(lambda *_: self._audio_probe_timer.start())
        if self._camera_device_combo is not None:
            self._camera_device_combo.currentIndexChanged.connect(self._on_camera_device_selected)
        if self._mic_device_combo is not None:
            self._mic_device_combo.currentIndexChanged.connect(self._on_mic_device_selected)
        resolution_combo.currentTextChanged.connect(lambda *_: self._camera_probe_timer.start())

        feedback_box = QWidget()
        feedback_layout = QVBoxLayout(feedback_box)
        feedback_layout.setContentsMargins(0, 8, 0, 0)
        feedback_layout.setSpacing(6)
        feedback_title = QLabel("Device Feedback")
        feedback_title.setObjectName("sectionTitle")
        self._camera_preview_label = QLabel("Camera preview not captured yet.\nSelect a camera or click Test Webcam.")
        self._camera_preview_label.setObjectName("viewerSurface")
        self._camera_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._camera_preview_label.setMinimumHeight(150)
        self._camera_preview_label.setWordWrap(True)
        self._audio_level_bar = QProgressBar()
        self._audio_level_bar.setRange(0, 100)
        self._audio_level_bar.setValue(0)
        self._audio_level_bar.setFormat("Audio level: %p%")
        self._audio_feedback_label = QLabel(
            "Audio input feedback\nSelect a microphone or click Test Audio to sample input."
        )
        self._audio_feedback_label.setObjectName("mutedText")
        self._audio_feedback_label.setWordWrap(True)
        caps = Recorder.capture_capabilities()
        capability_label = QLabel(
            "Runtime capture support: "
            + f"video={'yes' if caps.get('live_video_supported') else 'no'}, "
            + f"audio={'yes' if caps.get('live_audio_supported') else 'no'}"
        )
        capability_label.setObjectName("mutedText")
        capability_label.setWordWrap(True)
        feedback_layout.addWidget(feedback_title)
        feedback_layout.addWidget(capability_label)
        feedback_layout.addWidget(self._camera_preview_label)
        feedback_layout.addWidget(self._audio_level_bar)
        feedback_layout.addWidget(self._audio_feedback_label)
        form.addRow("", feedback_box)
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
        current_provider = str(self._settings.get("speech_to_text", {}).get("provider", "gpt-4o-mini-transcribe"))
        form.addRow(
            "Provider",
            self._register_combo(
                "stt_provider",
                ["gpt-4o-mini-transcribe", "openai_4o_transcribe", "whisper_replicate", "whisper_local"],
                current_provider,
            ),
        )
        form.addRow("Language", self._register_line("stt_language", self._settings["speech_to_text"]["language"]))
        hint = QLabel("Language codes: 'de' for German, 'en' for English. Whisper providers support more languages than OpenAI.")
        hint.setWordWrap(True)
        hint.setObjectName("mutedText")
        form.addRow("", hint)
        return tab

    def _build_frame_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.addRow("Interval (sec)", self._register_spin("frame_interval", self._settings["frame_extraction"]["interval_seconds"], 1, 3600))
        form.addRow("Max Frames", self._register_spin("frame_max", self._settings["frame_extraction"]["max_frames_per_screen"], 1, 500))
        form.addRow("Smart Selector", self._register_check("smart_enabled", self._settings["smart_selector"]["enabled"]))
        hint = QLabel("Smart Selector uses gesture detection, audio levels, and pixel differences to choose relevant frames.")
        hint.setWordWrap(True)
        hint.setObjectName("mutedText")
        form.addRow("", hint)
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

        # AI Analysis Enabled Checkbox
        form.addRow(
            "AI Analysis Enabled",
            self._register_check("analysis_enabled", self._settings["analysis"].get("enabled", False)),
        )

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
        hint = QLabel("Choose OpenRouter while Replicate access is blocked (403). When AI Analysis is disabled, only local processing (OCR, gestures, transcripts) will be used.")
        hint.setWordWrap(True)
        hint.setObjectName("mutedText")
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
        self._line("api_replicate").textChanged.connect(self._refresh_analysis_provider_options)
        self._line("api_openrouter").textChanged.connect(self._refresh_analysis_provider_options)

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
        self._api_status_states[key] = state
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
        self._refresh_analysis_provider_options()
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
        self._refresh_analysis_provider_options()

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
        tips = HelpSystem.get_context_tooltips("settings_fields")
        for key, text in tips.items():
            widget = self._fields.get(key)
            if widget is not None and hasattr(widget, "setToolTip"):
                widget.setToolTip(text)

    def _available_analysis_providers(self) -> list[str]:
        available: list[str] = []
        replicate_key_present = bool(self._line("api_replicate").text().strip())
        openrouter_key_present = bool(self._line("api_openrouter").text().strip())
        replicate_state = self._api_status_states.get("replicate_status", "idle")
        openrouter_state = self._api_status_states.get("openrouter_status", "idle")

        if replicate_key_present and replicate_state != "error":
            available.append("replicate")
        if openrouter_key_present and openrouter_state != "error":
            available.append("openrouter")
        return available

    def _set_combo_items(self, combo: QComboBox, items: list[str], previous_value: str) -> None:
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(items)
        if items:
            target_value = previous_value if previous_value in items else items[0]
            combo.setCurrentText(target_value)
            combo.setEnabled(True)
        else:
            combo.setEnabled(False)
        combo.blockSignals(False)

    def _refresh_analysis_provider_options(self) -> None:
        provider_items = self._available_analysis_providers()
        for key in ("analysis_provider", "quick_analysis_provider"):
            if key not in self._fields:
                continue
            combo = self._combo(key)
            previous_value = combo.currentText().strip()
            self._set_combo_items(combo, provider_items, previous_value)
            if provider_items:
                combo.setToolTip(
                    "Available providers with configured keys: " + ", ".join(provider_items)
                )
            else:
                combo.setToolTip(
                    "No provider key configured. Add a Replicate or OpenRouter key to enable provider selection."
                )
        if provider_items:
            self._sync_quick_start_from_fields()
        self._update_quick_start_summary()

    def _refresh_media_device_labels(self, *_args: object) -> None:
        camera_labels = self._device_labels("camera")
        mic_labels = self._device_labels("mic")
        self._populate_device_selector(self._camera_device_combo, camera_labels, "camera")
        self._populate_device_selector(self._mic_device_combo, mic_labels, "microphone")
        self._sync_device_selectors_from_indices()

        camera_text = self._device_label_text(device_type="camera", index=self._spin("camera_index").value())
        mic_text = self._device_label_text(device_type="mic", index=self._spin("mic_index").value())
        if self._camera_name_label is not None:
            self._camera_name_label.setText(camera_text)
        if self._mic_name_label is not None:
            self._mic_name_label.setText(mic_text)
        self._update_device_feedback_widgets()

    def _device_label_text(self, device_type: str, index: int) -> str:
        labels = self._device_labels(device_type)
        if not labels:
            return "Detected device: names unavailable (Qt Multimedia not available)"
        if 0 <= index < len(labels):
            return f"Detected device: {labels[index]} (index {index})"
        return (
            f"Detected device: index {index} not found. Available: "
            + ", ".join(f"{i}={name}" for i, name in enumerate(labels))
        )

    def _device_labels(self, device_type: str) -> list[str]:
        if QMediaDevices is None:
            return []
        try:
            if device_type == "camera":
                devices = QMediaDevices.videoInputs()
            else:
                devices = QMediaDevices.audioInputs()
        except Exception:
            return []
        labels: list[str] = []
        for device in devices:
            try:
                labels.append(str(device.description()))
            except Exception:
                labels.append("Unknown device")
        return labels

    def _populate_device_selector(
        self,
        combo: QComboBox | None,
        labels: list[str],
        device_label: str,
    ) -> None:
        if combo is None:
            return
        previous_data = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        if labels:
            for idx, label in enumerate(labels):
                combo.addItem(f"{idx}: {label}", idx)
            combo.setEnabled(True)
            if previous_data is not None:
                match_index = combo.findData(previous_data)
                if match_index >= 0:
                    combo.setCurrentIndex(match_index)
        else:
            if QMediaDevices is None:
                combo.addItem(f"No {device_label} list available (Qt Multimedia missing)", -1)
            else:
                combo.addItem(f"No {device_label} devices detected", -1)
            combo.setEnabled(False)
        combo.blockSignals(False)

    def _sync_device_selectors_from_indices(self, *_args: object) -> None:
        self._sync_device_selector(self._camera_device_combo, self._spin("camera_index").value())
        self._sync_device_selector(self._mic_device_combo, self._spin("mic_index").value())
        self._update_device_feedback_widgets()

    def _sync_device_selector(self, combo: QComboBox | None, index_value: int) -> None:
        if combo is None or not combo.isEnabled():
            return
        match_index = combo.findData(index_value)
        if match_index < 0 or combo.currentIndex() == match_index:
            return
        combo.blockSignals(True)
        combo.setCurrentIndex(match_index)
        combo.blockSignals(False)

    def _on_camera_device_selected(self, combo_index: int) -> None:
        import logging
        logging.getLogger(__name__).debug(f"[_on_camera_device_selected] combo_index={combo_index}")
        self._apply_selected_device_index(self._camera_device_combo, "camera_index", combo_index)
        self._announce_device_feedback("Camera selection updated.")
        self._camera_probe_timer.start()

    def _on_mic_device_selected(self, combo_index: int) -> None:
        import logging
        logging.getLogger(__name__).debug(f"[_on_mic_device_selected] combo_index={combo_index}")
        self._apply_selected_device_index(self._mic_device_combo, "mic_index", combo_index)
        self._announce_device_feedback("Microphone selection updated.")
        self._audio_probe_timer.start()

    def _apply_selected_device_index(self, combo: QComboBox | None, field_key: str, combo_index: int) -> None:
        if combo is None or combo_index < 0:
            return
        device_index = combo.itemData(combo_index)
        if not isinstance(device_index, int) or device_index < 0:
            return
        spin = self._spin(field_key)
        if spin.value() != device_index:
            spin.setValue(device_index)

    def _selected_combo_label(self, combo: QComboBox | None) -> str:
        if combo is None:
            return "Not available"
        if combo.currentIndex() < 0:
            return "Not selected"
        return combo.currentText()

    def _stop_device_monitors(self) -> None:
        self._camera_probe_timer.stop()
        self._audio_probe_timer.stop()
        self._device_monitor_ui_timer.stop()
        self._camera_preview_monitor.stop()
        self._audio_level_monitor.stop()

    def _refresh_camera_preview_pipeline(self) -> None:
        import logging
        logging.getLogger(__name__).debug("Starting _refresh_camera_preview_pipeline")
        camera_index = int(self._spin("camera_index").value())
        probe_started = self._probe_camera_resolution_options(camera_index)
        if not probe_started:
            resolution = self._combo("webcam_resolution").currentText().strip() or "1080p"
            self._camera_preview_pixmap = None
            self._camera_preview_monitor.start(camera_index=camera_index, resolution=resolution)
            if self._camera_preview_label is not None and not self._camera_preview_monitor.is_running():
                self._camera_preview_label.setPixmap(QPixmap())
                self._camera_preview_label.setText(
                    "Camera Preview\n"
                    f"Selected: {self._selected_combo_label(self._camera_device_combo)}\n"
                    f"Monitor failed: {self._camera_preview_monitor.get_last_error() or 'Unknown error'}"
                )

    def _restart_audio_monitor(self) -> None:
        import logging
        logging.getLogger(__name__).debug("Starting _restart_audio_monitor")
        mic_index = int(self._spin("mic_index").value())
        self._audio_level_monitor.start(mic_index)
        if self._audio_feedback_label is not None and not self._audio_level_monitor.is_running():
            self._audio_feedback_label.setText(
                "Audio Input Feedback\n"
                f"Selected source: {self._selected_combo_label(self._mic_device_combo)}\n"
                f"Monitor failed: {self._audio_level_monitor.get_last_error() or 'Unknown error'}"
            )
        if self._audio_level_bar is not None and not self._audio_level_monitor.is_running():
            self._audio_level_bar.setValue(0)

    def _refresh_live_device_feedback(self) -> None:
        frame = self._camera_preview_monitor.get_last_frame()
        if frame is not None:
            self._set_camera_preview_from_frame(frame)
        elif self._camera_preview_label is not None and self._camera_preview_pixmap is None:
            error = self._camera_preview_monitor.get_last_error()
            if error:
                self._camera_preview_label.setText(
                    "Camera Preview\n"
                    f"Selected: {self._selected_combo_label(self._camera_device_combo)}\n"
                    f"{error}"
                )

        level = self._audio_level_monitor.get_level()
        if self._audio_level_bar is not None:
            self._audio_level_bar.setValue(max(0, min(100, int(level * 100))))
        if self._audio_feedback_label is not None:
            status = "live" if self._audio_level_monitor.is_running() else "idle"
            err = self._audio_level_monitor.get_last_error()
            error_line = f"\nMonitor error: {err}" if err else ""
            self._audio_feedback_label.setText(
                "Audio Input Feedback\n"
                f"Selected source: {self._selected_combo_label(self._mic_device_combo)}\n"
                f"Continuous monitor: {status}, level {int(level * 100)}%{error_line}"
            )

    def _probe_camera_resolution_options(self, camera_index: int) -> bool:
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"Requested resolution probe for camera {camera_index}")
        if self._camera_resolution_probe_active:
            logger.debug("Resolution probe already active, skipping.")
            return False
        # Cache per camera index to avoid expensive repeated probing while preview updates.
        if camera_index in self._camera_resolution_cache:
            logger.debug("Using cached resolutions.")
            self._apply_camera_resolution_options(
                self._camera_resolution_cache[camera_index],
                source_message="Using cached camera-specific resolutions.",
            )
            return False
        self._camera_resolution_probe_active = True
        logger.debug("Stopping camera preview for resolution probe...")
        was_running = self._camera_preview_monitor.is_running()
        if was_running:
            self._camera_preview_monitor.stop()

        self._start_camera_probe_thread(camera_index)
        return True

    def _start_camera_probe_thread(self, camera_index: int) -> None:
        if self._camera_probe_thread is not None and self._camera_probe_thread.isRunning():
            self._camera_probe_thread.quit()
            self._camera_probe_thread.wait()

        self._camera_probe_thread = QThread(self)
        self._camera_probe_worker = _CameraResolutionWorker(camera_index)
        self._camera_probe_worker.moveToThread(self._camera_probe_thread)
        self._camera_probe_thread.started.connect(self._camera_probe_worker.run)
        self._camera_probe_worker.finished.connect(self._on_camera_probe_finished)
        self._camera_probe_worker.finished.connect(self._camera_probe_thread.quit)
        self._camera_probe_thread.finished.connect(self._camera_probe_worker.deleteLater)
        self._camera_probe_thread.finished.connect(self._camera_probe_thread.deleteLater)
        self._camera_probe_thread.start()

    def _on_camera_probe_finished(self, camera_index: int, options: list[str], message: str) -> None:
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"Probe finished for camera {camera_index}: {options}, message={message}")
        self._camera_probe_thread = None
        self._camera_probe_worker = None
        self._camera_resolution_cache[camera_index] = options
        self._camera_resolution_probe_active = False
        self._apply_camera_resolution_options(options, source_message=message)
        
        # Start the preview monitor if we are still on the same camera
        current_camera = int(self._spin("camera_index").value())
        if current_camera == camera_index:
            resolution = self._combo("webcam_resolution").currentText().strip() or "1080p"
            self._camera_preview_pixmap = None
            self._camera_preview_monitor.start(camera_index=camera_index, resolution=resolution)
            if self._camera_preview_label is not None and not self._camera_preview_monitor.is_running():
                self._camera_preview_label.setPixmap(QPixmap())
                self._camera_preview_label.setText(
                    "Camera Preview\n"
                    f"Selected: {self._selected_combo_label(self._camera_device_combo)}\n"
                    f"Monitor failed: {self._camera_preview_monitor.get_last_error() or 'Unknown error'}"
                )

    def _apply_camera_resolution_options(self, options: list[str], source_message: str = "") -> None:
        if "webcam_resolution" not in self._fields:
            return
        combo = self._combo("webcam_resolution")
        previous = combo.currentText().strip() or str(self._settings.get("webcam", {}).get("resolution", "1080p"))
        self._set_combo_items(combo, options, previous)
        if self._resolution_info_label is not None:
            self._resolution_info_label.setText(
                source_message or "Camera-specific resolution options loaded."
            )

    def _update_device_feedback_widgets(self) -> None:
        camera_line = self._selected_combo_label(self._camera_device_combo)
        mic_line = self._selected_combo_label(self._mic_device_combo)
        if self._camera_preview_label is not None:
            if self._camera_preview_pixmap is None:
                self._camera_preview_label.setPixmap(QPixmap())
                self._camera_preview_label.setText(
                    "Camera Preview\n"
                    f"Selected: {camera_line}\n"
                    "No preview snapshot yet. Click Test Webcam or re-select the device."
                )
        if self._audio_feedback_label is not None:
            self._audio_feedback_label.setText(
                "Audio Input Feedback\n"
                f"Selected source: {mic_line}\n"
                "Continuous monitoring starts automatically. Test Audio runs an additional explicit check."
            )

    def _announce_device_feedback(self, text: str) -> None:
        if self._audio_feedback_label is None:
            return
        current = self._audio_feedback_label.text()
        self._audio_feedback_label.setText(f"{current}\n\n{text}")
        self._device_feedback_timer.start()

    def _clear_device_feedback_hint(self) -> None:
        self._update_device_feedback_widgets()

    def _capture_camera_preview_snapshot(self) -> None:
        camera_index = self._spin("camera_index").value()
        resolution = self._combo("webcam_resolution").currentText()
        live_frame = self._camera_preview_monitor.get_last_frame()
        if live_frame is not None and self._set_camera_preview_from_frame(live_frame):
            return
        result = Recorder.capture_single_frame(
            camera_index=int(camera_index),
            resolution=str(resolution),
            timeout_seconds=0.8,
        )
        if self._camera_preview_label is None:
            return
        if bool(result.get("ok")) and result.get("frame") is not None:
            if self._set_camera_preview_from_frame(result.get("frame")):
                self._camera_preview_label.setToolTip(str(result.get("message", "")))
                self._announce_device_feedback("Camera preview snapshot updated.")
                return
        self._camera_preview_pixmap = None
        self._camera_preview_label.setPixmap(QPixmap())
        self._camera_preview_label.setText(
            "Camera Preview\n"
            f"Selected: {self._selected_combo_label(self._camera_device_combo)}\n"
            f"Preview failed: {result.get('message', 'Unknown error')}"
        )

    def _capture_audio_level_snapshot(self) -> None:
        mic_index = self._spin("mic_index").value()
        result = Recorder.sample_audio_input_level(int(mic_index), duration_seconds=0.25)
        if self._audio_level_bar is not None:
            level = float(result.get("level", 0.0))
            self._audio_level_bar.setValue(max(0, min(100, int(level * 100))))
        if self._audio_feedback_label is not None:
            status = "OK" if bool(result.get("ok")) else "FAILED"
            self._audio_feedback_label.setText(
                "Audio Input Feedback\n"
                f"Selected source: {self._selected_combo_label(self._mic_device_combo)}\n"
                f"Last sample: {status} - {result.get('message', 'No message')}"
            )

    def _set_camera_preview_from_frame(self, frame: object) -> bool:
        if self._camera_preview_label is None:
            return False
        if frame is None or not hasattr(frame, "shape"):
            return False
        try:
            array = frame
            height = int(array.shape[0])
            width = int(array.shape[1])
            if len(array.shape) < 3 or int(array.shape[2]) < 3:
                return False
            rgb = array[:, :, ::-1]
            bytes_per_line = int(rgb.strides[0])
            image = QImage(
                rgb.data,
                width,
                height,
                bytes_per_line,
                QImage.Format.Format_RGB888,
            ).copy()
            pixmap = QPixmap.fromImage(image)
            self._camera_preview_pixmap = pixmap
            scaled = pixmap.scaled(
                self._camera_preview_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._camera_preview_label.setText("")
            self._camera_preview_label.setPixmap(scaled)
            return True
        except Exception:
            return False

    def _on_test_webcam_device(self) -> None:
        camera_index = self._spin("camera_index").value()
        labels = self._device_labels("camera")
        selected_label = (
            labels[camera_index] if 0 <= camera_index < len(labels) else f"index {camera_index} not detected"
        )
        resolution = self._combo("webcam_resolution").currentText()
        live_frame = self._camera_preview_monitor.get_last_frame()
        if live_frame is not None:
            result = {"ok": True, "message": "Using current live preview frame.", "frame": live_frame}
            self._set_camera_preview_from_frame(live_frame)
        else:
            result = Recorder.capture_single_frame(int(camera_index), str(resolution), timeout_seconds=1.2)
            if bool(result.get("ok")) and result.get("frame") is not None:
                self._set_camera_preview_from_frame(result.get("frame"))
        lines = [
            f"Selected camera index: {camera_index}",
            f"Detected camera: {selected_label}",
            f"Selected resolution preset: {resolution}",
            f"Live webcam test: {'OK' if bool(result.get('ok')) else 'FAILED'}",
            f"Result: {result.get('message', 'No message')}",
            "",
            "Recorder backend uses live capture when runtime dependencies/devices are available,",
            "otherwise it falls back to placeholder files per stream.",
        ]
        self._announce_device_feedback("Webcam diagnostic executed.")
        import logging
        logging.getLogger(__name__).debug(f"Webcam diagnostic lines: {lines}")
        QMessageBox.information(self, "Webcam Test", "\n".join(lines))
        # Deaktiviere Kamera Preview nach Test
        self._camera_preview_monitor.stop()

    def _on_test_audio_device(self) -> None:
        mic_index = self._spin("mic_index").value()
        labels = self._device_labels("mic")
        selected_label = labels[mic_index] if 0 <= mic_index < len(labels) else f"index {mic_index} not detected"

        sample_result = Recorder.sample_audio_input_level(int(mic_index), duration_seconds=0.5)
        if self._audio_level_bar is not None:
            self._audio_level_bar.setValue(max(0, min(100, int(float(sample_result.get("level", 0.0)) * 100))))

        pipeline_ok = False
        created_files: list[str] = []
        error_text = ""
        backend_mode = ""
        backend_notes: list[str] = []
        try:
            with tempfile.TemporaryDirectory(prefix="screenreview-audio-test-") as tmpdir:
                rec = Recorder()
                rec.set_output_dir(Path(tmpdir))
                rec.start(
                    camera_index=int(self._spin("camera_index").value()),
                    mic_index=int(mic_index),
                    resolution=str(self._combo("webcam_resolution").currentText()),
                )
                time.sleep(0.35)
                video_path, audio_path = rec.stop()
                pipeline_ok = video_path.exists() and audio_path.exists()
                backend_mode = rec.get_backend_mode()
                backend_notes = rec.get_backend_notes()
                created_files = [str(video_path), str(audio_path)]
        except Exception as exc:  # pragma: no cover - runtime diagnostic path
            error_text = str(exc)

        lines = [
            f"Selected microphone index: {mic_index}",
            f"Detected microphone: {selected_label}",
            f"Live audio sample: {'OK' if bool(sample_result.get('ok')) else 'FAILED'}",
            f"Audio sample result: {sample_result.get('message', 'No message')}",
            f"Recorder pipeline test: {'OK' if pipeline_ok else 'FAILED'}",
        ]
        if backend_mode:
            lines.append(f"Recorder backend mode: {backend_mode}")
        if created_files:
            lines.extend(["", "Created test output files:"])
            lines.extend([f"- {path}" for path in created_files])
        if backend_notes:
            lines.extend(["", "Recorder backend notes:"])
            lines.extend([f"- {note}" for note in backend_notes[:5]])
        if error_text:
            lines.extend(["", f"Error: {error_text}"])
        self._announce_device_feedback("Audio diagnostic executed.")
        import logging
        logging.getLogger(__name__).debug(f"Audio diagnostic lines: {lines}")
        QMessageBox.information(self, "Audio Test", "\n".join(lines))

    def _apply_tab_tooltips(self) -> None:
        for index in range(self.tab_widget.count()):
            tab_name = self.tab_widget.tabText(index)
            self.tab_widget.tabBar().setTabToolTip(
                index,
                HelpSystem.get_tooltip("settings_tabs", tab_name),
            )

    def _tab_help_context(self, tab_name: str) -> str:
        return f"settings.tab.{tab_name}"

    def _add_tab_help_buttons(self) -> None:
        tab_bar = self.tab_widget.tabBar()
        for index in range(self.tab_widget.count()):
            tab_name = self.tab_widget.tabText(index)
            help_button = QPushButton("?")
            help_button.setObjectName("tabHelpButton")
            help_button.setFixedSize(22, 22)
            help_button.setCursor(Qt.CursorShape.PointingHandCursor)
            help_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            help_button.setToolTip(f"Open help for '{tab_name}' tab.")
            help_button.setStyleSheet(
                """
                QPushButton#tabHelpButton {
                    background: #eff6ff;
                    color: #1d4ed8;
                    border: 1px solid #bfdbfe;
                    border-radius: 11px;
                    font-weight: 700;
                    padding: 0px;
                }
                QPushButton#tabHelpButton:hover {
                    background: #dbeafe;
                    border-color: #93c5fd;
                }
            QComboBox#settingsModeCombo {
                background: white;
                border: 1px solid #d0d7e2;
            }
            """
        )
            help_context = self._tab_help_context(tab_name)
            help_button.clicked.connect(
                lambda _checked=False, context=help_context: HelpSystem.show_help_dialog(context, self)
            )
            tab_bar.setTabButton(index, QTabBar.ButtonPosition.RightSide, help_button)

    def _sync_quick_start_into_fields(self) -> None:
        if "quick_viewport_mode" in self._fields:
            self._combo("viewport_mode").setCurrentText(self._combo("quick_viewport_mode").currentText())
        if "quick_analysis_provider" in self._fields:
            quick_provider = self._combo("quick_analysis_provider").currentText().strip()
            if quick_provider:
                self._combo("analysis_provider").setCurrentText(quick_provider)
        if "quick_analysis_model" in self._fields:
            self._combo("analysis_model").setCurrentText(self._combo("quick_analysis_model").currentText())

    def _sync_quick_start_from_fields(self) -> None:
        if "quick_viewport_mode" in self._fields:
            self._combo("quick_viewport_mode").setCurrentText(self._combo("viewport_mode").currentText())
        if "quick_analysis_provider" in self._fields:
            self._combo("quick_analysis_provider").setCurrentText(self._combo("analysis_provider").currentText())
        if "quick_analysis_model" in self._fields:
            self._combo("quick_analysis_model").setCurrentText(self._combo("analysis_model").currentText())

    def _reset_to_defaults(self) -> None:
        self._combo("camera_device").setCurrentIndex(0)
        self._combo("webcam_resolution").setCurrentText("1080p")
        self._combo("mic_device").setCurrentIndex(0)
        self._combo("stt_provider").setCurrentText("gpt-4o-mini-transcribe")
        self._line("stt_language").setText("de")
        self._spin("frame_interval").setValue(5)

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
            self._combo("stt_provider").setCurrentText("gpt-4o-mini-transcribe")
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
