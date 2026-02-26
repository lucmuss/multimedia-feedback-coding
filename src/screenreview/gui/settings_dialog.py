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
    QFrame,
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


class _GoProDetectionWorker(QObject):
    """Worker object for running GoPro RNDIS detection without UI freeze."""
    finished = pyqtSignal(dict)

    def run(self) -> None:
        try:
            from screenreview.pipeline.recorder import Recorder
            result = Recorder.detect_gopro_url()
            self.finished.emit(result)
        except Exception as exc:
            self.finished.emit({"ok": False, "message": f"Detection failed: {exc}"})


class _CameraResolutionWorker(QObject):
    """Worker object for running camera resolution probes without UI freeze."""
    finished = pyqtSignal(int, list, str)

    def __init__(self, camera_index: int, custom_url: str = "") -> None:
        super().__init__()
        self._camera_index = camera_index
        self._custom_url = custom_url

    def run(self) -> None:
        try:
            import logging
            logger = logging.getLogger("screenreview.gui.settings_dialog")
            logger.debug(f"[_CameraResolutionWorker] Probing camera source {self._custom_url or self._camera_index}")
            from screenreview.pipeline.recorder import Recorder
            result = Recorder.probe_camera_resolution_options(
                self._camera_index, 
                custom_url=self._custom_url
            )
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
        "Gesture Detection",
        "OCR",
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
        
        self.setStyleSheet("""
            QFormLayout QLabel { font-weight: bold; }
            QLabel#sectionTitle { font-weight: bold; font-size: 14px; }
            QLabel#mutedText { font-weight: normal; color: #6b7280; }
        """)
        self.resize(780, 600)
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
        self._camera_resolution_cache: dict[str, list[str]] = {}
        self._camera_resolution_probe_active = False
        
        self._openai_client = OpenAIClient()
        self._openrouter_client = OpenRouterClient()
        self._replicate_client = ReplicateClient()
        
        self._api_validation_thread: QThread | None = None
        self._api_validation_worker: _ApiValidationWorker | None = None
        
        self._gopro_detection_thread: QThread | None = None
        self._gopro_detection_worker: _GoProDetectionWorker | None = None
        
        self._camera_probe_thread: QThread | None = None
        self._camera_probe_worker: _CameraResolutionWorker | None = None
        
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
        self._camera_probe_timer.setInterval(400)
        self._camera_probe_timer.timeout.connect(self._refresh_camera_preview_pipeline)
        
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
        self.mode_combo.currentTextChanged.connect(self._apply_settings_mode)
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Settings Mode"))
        mode_row.addWidget(self.mode_combo)
        mode_row.addStretch(1)

        layout = QVBoxLayout(self)
        top_row = QHBoxLayout()
        top_row.addLayout(mode_row)
        top_row.addStretch(1)
        top_row.addWidget(self.button_box)
        layout.addLayout(top_row)
        layout.addWidget(self.tab_widget, 1)

        self._apply_field_tooltips()
        self._connect_api_key_live_checks()
        self._refresh_analysis_provider_options()
        self._refresh_media_device_labels()
        self._apply_settings_mode("Advanced") 
        self.mode_combo.setCurrentText("Advanced")
        self._schedule_api_validation()

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        self._camera_probe_timer.start()
        self._audio_probe_timer.start()
        if not self._device_monitor_ui_timer.isActive(): self._device_monitor_ui_timer.start()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        if self._camera_preview_pixmap and self._camera_preview_label:
            scaled = self._camera_preview_pixmap.scaled(self._camera_preview_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self._camera_preview_label.setPixmap(scaled)

    def get_settings(self) -> dict[str, Any]: return deepcopy(self._settings)

    def accept(self) -> None:  # type: ignore[override]
        self._apply_into_state()
        self._stop_all_background_tasks()
        super().accept()

    def reject(self) -> None:  # type: ignore[override]
        self._stop_all_background_tasks()
        super().reject()

    def _stop_all_background_tasks(self) -> None:
        self._stop_device_monitors()
        self._stop_api_validation_thread()
        self._stop_gopro_detection()
        self._stop_camera_probe()

    def _stop_device_monitors(self) -> None:
        """Stop live camera and audio monitors and their UI update timer."""
        if hasattr(self, "_device_monitor_ui_timer") and self._device_monitor_ui_timer.isActive():
            self._device_monitor_ui_timer.stop()
        if hasattr(self, "_camera_preview_monitor"):
            self._camera_preview_monitor.stop()
        if hasattr(self, "_audio_level_monitor"):
            self._audio_level_monitor.stop()

    def _apply_into_state(self) -> None:
        self._sync_quick_start_into_fields()
        self._settings["api_keys"]["openai"] = self._line("api_openai").text()
        self._settings["api_keys"]["replicate"] = self._line("api_replicate").text()
        self._settings["api_keys"]["openrouter"] = self._line("api_openrouter").text()
        self._settings["viewport"]["mode"] = self._combo("viewport_mode").currentText()
        self._settings["webcam"]["camera_index"] = self._spin("camera_index").value()
        self._settings["webcam"]["custom_url"] = self._line("custom_url").text().strip()
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
        self._settings["analysis"]["provider"] = self._combo("analysis_provider").currentText()
        self._settings["analysis"]["model"] = self._combo("analysis_model").currentText()
        self._settings["cost"]["budget_limit_euro"] = self._dspin("budget_limit").value()
        self._settings["cost"]["warning_at_euro"] = self._dspin("budget_warning").value()
        self._settings["cost"]["auto_stop_at_limit"] = self._check("budget_autostop").isChecked()
        self._settings["recording"]["overwrite_recordings"] = self._check("recording_overwrite").isChecked()
        self._settings["export"]["auto_export_after_analysis"] = self._check("export_auto").isChecked()
        self._settings["export"]["format"] = self._combo("export_format").currentText()

        hotkeys_editor = self._plain("hotkeys_editor").toPlainText().strip().splitlines()
        for line in hotkeys_editor:
            if ":" in line:
                k, v = line.split(":", 1)
                self._settings["hotkeys"][k.strip()] = v.strip()

    def _create_tab(self, name: str) -> QWidget:
        if name == "Quick Start": return self._build_quick_start_tab()
        if name == "API Keys": return self._build_api_tab()
        if name == "Webcam & Audio": return self._build_webcam_tab()
        if name == "Viewport": return self._build_viewport_tab()
        if name == "Speech-to-Text": return self._build_stt_tab()
        if name == "Frame Extraction": return self._build_frame_tab()
        if name == "Gesture Detection": return self._build_gesture_tab()
        if name == "OCR": return self._build_ocr_tab()
        if name == "AI Analysis": return self._build_analysis_tab()
        if name == "Cost": return self._build_cost_tab()
        if name == "Hotkeys": return self._build_hotkeys_tab()
        if name == "Export": return self._build_export_tab()
        return QWidget()

    def _build_quick_start_tab(self) -> QWidget:
        tab = QWidget(); layout = QVBoxLayout(tab); layout.setSpacing(10)
        title = QLabel("Quick Start"); title.setObjectName("sectionTitle"); layout.addWidget(title)
        project_label = QLabel(str(self._project_dir) if self._project_dir else "No project selected"); project_label.setWordWrap(True); layout.addWidget(QLabel("Project Folder")); layout.addWidget(project_label)
        quick_form = QFormLayout()
        quick_form.addRow("Viewport", self._register_combo("quick_viewport_mode", ["mobile", "desktop"], self._settings["viewport"]["mode"]))
        quick_form.addRow("AI Provider", self._register_combo("quick_analysis_provider", ["replicate", "openrouter"], str(self._settings["analysis"].get("provider", "replicate"))))
        quick_form.addRow("AI Model", self._register_combo("quick_analysis_model", ["llama_32_vision", "qwen_vl", "gpt4o_vision"], self._settings["analysis"]["model"]))
        layout.addLayout(quick_form)
        preset_row = QHBoxLayout(); self._fields["quick_preset"] = QComboBox(); self._combo("quick_preset").addItems(["Balanced (Recommended)", "Fast & Cheap", "High Accuracy", "Local-Only"])
        apply_btn = QPushButton("Apply Preset"); apply_btn.clicked.connect(self._apply_selected_preset); preset_row.addWidget(QLabel("Preset")); preset_row.addWidget(self._combo("quick_preset"), 1); preset_row.addWidget(apply_btn); layout.addLayout(preset_row)
        btn_row = QHBoxLayout(); test_conn = QPushButton("Test Connections"); test_conn.clicked.connect(self._on_test_connections); preflight = QPushButton("Run Preflight Check"); preflight.clicked.connect(self._on_run_preflight); btn_row.addWidget(test_conn); btn_row.addWidget(preflight); layout.addLayout(btn_row)
        self._quick_summary_label = QLabel(""); self._quick_summary_label.setWordWrap(True); layout.addWidget(self._quick_summary_label); layout.addStretch(1)
        return tab

    def _build_api_tab(self) -> QWidget:
        tab = QWidget(); form = QFormLayout(tab)
        form.addRow("OpenAI Key", self._register_line("api_openai", self._settings["api_keys"]["openai"], True))
        form.addRow("Replicate Key", self._register_line("api_replicate", self._settings["api_keys"]["replicate"], True))
        form.addRow("OpenRouter Key", self._register_line("api_openrouter", self._settings["api_keys"].get("openrouter", ""), True))
        form.addRow("OpenAI Status", self._create_status_row("openai_status"))
        form.addRow("Replicate Status", self._create_status_row("replicate_status"))
        form.addRow("OpenRouter Status", self._create_status_row("openrouter_status"))
        form.addRow("Model Status", self._create_status_row("model_status"))
        return tab

    def _build_webcam_tab(self) -> QWidget:
        tab = QWidget(); form = QFormLayout(tab)
        camera_index_spin = self._register_spin("camera_index", self._settings["webcam"]["camera_index"], 0, 16)
        mic_index_spin = self._register_spin("mic_index", self._settings["webcam"]["microphone_index"], 0, 32)
        camera_row = QWidget(); camera_layout = QVBoxLayout(camera_row); camera_layout.setContentsMargins(0, 0, 0, 0); camera_layout.setSpacing(4)
        self._camera_device_combo = QComboBox(); self._camera_name_label = QLabel("Detected device: loading..."); camera_layout.addWidget(self._camera_device_combo); camera_layout.addWidget(camera_index_spin); camera_layout.addWidget(self._camera_name_label); form.addRow("Camera Index", camera_row)
        custom_url_field = self._register_line("custom_url", str(self._settings["webcam"].get("custom_url", "")))
        detect_btn = QPushButton("Auto-Detect GoPro (RNDIS)"); detect_btn.clicked.connect(self._on_detect_gopro)
        url_layout = QHBoxLayout(); url_layout.addWidget(custom_url_field, 1); url_layout.addWidget(detect_btn); url_cont = QWidget(); url_cont.setLayout(url_layout); form.addRow("Custom Stream URL", url_cont)
        url_hint = QLabel("Optional: Enter URL for GoPro (udp://@0.0.0.0:8554) or IP-Cam."); url_hint.setWordWrap(True); url_hint.setObjectName("mutedText"); form.addRow("", url_hint)
        mic_row = QWidget(); mic_layout = QVBoxLayout(mic_row); mic_layout.setContentsMargins(0, 0, 0, 0); self._mic_device_combo = QComboBox(); self._mic_name_label = QLabel("Detected device: loading..."); mic_layout.addWidget(self._mic_device_combo); mic_layout.addWidget(mic_index_spin); mic_layout.addWidget(self._mic_name_label); form.addRow("Microphone Index", mic_row)
        res_row = QWidget(); res_layout = QVBoxLayout(res_row); res_layout.setContentsMargins(0, 0, 0, 0); res_combo = self._register_combo("webcam_resolution", ["720p", "1080p", "4k"], self._settings["webcam"]["resolution"]); self._resolution_info_label = QLabel("Probing resolutions..."); res_layout.addWidget(res_combo); res_layout.addWidget(self._resolution_info_label); form.addRow("Resolution", res_row)
        diag_row = QHBoxLayout(); test_webcam = QPushButton("Test Webcam"); test_webcam.clicked.connect(self._on_test_webcam_device); test_audio = QPushButton("Test Audio"); test_audio.clicked.connect(self._on_test_audio_device); diag_row.addWidget(test_webcam); diag_row.addWidget(test_audio); diag_row.addStretch(1); diag_box = QWidget(); diag_box.setLayout(diag_row); form.addRow("Diagnostics", diag_box)
        camera_index_spin.valueChanged.connect(lambda: [self._refresh_media_device_labels(), self._camera_probe_timer.start()])
        mic_index_spin.valueChanged.connect(lambda: [self._refresh_media_device_labels(), self._audio_probe_timer.start()])
        self._camera_device_combo.currentIndexChanged.connect(self._on_camera_device_selected)
        self._mic_device_combo.currentIndexChanged.connect(self._on_mic_device_selected)
        custom_url_field.textChanged.connect(lambda: self._camera_probe_timer.start())
        res_combo.currentTextChanged.connect(lambda: self._camera_probe_timer.start())
        feedback_box = QWidget(); feedback_layout = QVBoxLayout(feedback_box); feedback_layout.setContentsMargins(0, 8, 0, 0)
        feedback_title = QLabel("Device Feedback"); feedback_title.setObjectName("sectionTitle"); self._camera_preview_label = QLabel("Camera preview not captured yet."); self._camera_preview_label.setObjectName("viewerSurface"); self._camera_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter); self._camera_preview_label.setMinimumHeight(150); self._camera_preview_label.setWordWrap(True); self._audio_level_bar = QProgressBar(); self._audio_level_bar.setRange(0, 100); self._audio_feedback_label = QLabel("Audio input feedback")
        feedback_layout.addWidget(feedback_title); feedback_layout.addWidget(self._camera_preview_label); feedback_layout.addWidget(self._audio_level_bar); feedback_layout.addWidget(self._audio_feedback_label); form.addRow("", feedback_box)
        return tab

    def _build_viewport_tab(self) -> QWidget:
        tab = QWidget(); form = QFormLayout(tab); form.addRow("Mode", self._register_combo("viewport_mode", ["mobile", "desktop"], self._settings["viewport"]["mode"])); return tab

    def _build_stt_tab(self) -> QWidget:
        tab = QWidget(); form = QFormLayout(tab); form.addRow("Provider", self._register_combo("stt_provider", ["gpt-4o-mini-transcribe", "openai_4o_transcribe", "whisper_replicate", "whisper_local"], str(self._settings.get("speech_to_text", {}).get("provider", "gpt-4o-mini-transcribe")))); form.addRow("Language", self._register_line("stt_language", self._settings["speech_to_text"]["language"])); return tab

    def _build_frame_tab(self) -> QWidget:
        tab = QWidget(); form = QFormLayout(tab); form.addRow("Interval (sec)", self._register_spin("frame_interval", self._settings["frame_extraction"]["interval_seconds"], 1, 3600)); form.addRow("Max Frames", self._register_spin("frame_max", self._settings["frame_extraction"]["max_frames_per_screen"], 1, 500)); form.addRow("Smart Selector", self._register_check("smart_enabled", self._settings["smart_selector"]["enabled"])); return tab

    def _build_gesture_tab(self) -> QWidget:
        tab = QWidget(); form = QFormLayout(tab); form.addRow("Gesture Detection", self._register_check("gesture_enabled", self._settings["gesture_detection"]["enabled"])); form.addRow("Gesture Sensitivity", self._register_dspin("gesture_sensitivity", float(self._settings["gesture_detection"]["sensitivity"]), 0.0, 1.0, 0.05)); return tab

    def _build_ocr_tab(self) -> QWidget:
        tab = QWidget(); form = QFormLayout(tab); form.addRow("OCR Enabled", self._register_check("ocr_enabled", self._settings["ocr"]["enabled"])); from screenreview.pipeline.ocr_engines import OcrEngineFactory; available = OcrEngineFactory.get_available_engines(); options = ["auto"] + available; form.addRow("OCR Engine", self._register_combo("ocr_engine", options, str(self._settings.get("ocr", {}).get("engine", "auto")))); return tab

    def _build_analysis_tab(self) -> QWidget:
        tab = QWidget(); form = QFormLayout(tab); form.addRow("AI Analysis Enabled", self._register_check("analysis_enabled", self._settings["analysis"].get("enabled", False))); form.addRow("Provider", self._register_combo("analysis_provider", ["replicate", "openrouter"], str(self._settings["analysis"].get("provider", "replicate")))); form.addRow("Model", self._register_combo("analysis_model", ["llama_32_vision", "qwen_vl", "gpt4o_vision"], self._settings["analysis"]["model"])); return tab

    def _build_cost_tab(self) -> QWidget:
        tab = QWidget(); form = QFormLayout(tab); form.addRow("Budget Limit (EUR)", self._register_dspin("budget_limit", 10.0, 0.0, 1000.0, 0.1)); form.addRow("Warning At (EUR)", self._register_dspin("budget_warning", 5.0, 0.0, 1000.0, 0.1)); form.addRow("Auto Stop", self._register_check("budget_autostop", False)); return tab

    def _build_hotkeys_tab(self) -> QWidget:
        tab = QWidget(); layout = QVBoxLayout(tab); layout.addWidget(QLabel("action: shortcut")); editor = QPlainTextEdit(); editor.setPlainText("\n".join(f"{k}: {v}" for k, v in self._settings["hotkeys"].items())); self._fields["hotkeys_editor"] = editor; layout.addWidget(editor, 1); return tab

    def _build_export_tab(self) -> QWidget:
        tab = QWidget(); form = QFormLayout(tab); form.addRow("Overwrite old recordings", self._register_check("recording_overwrite", self._settings.get("recording", {}).get("overwrite_recordings", True))); form.addRow(QFrame()); form.addRow("Format", self._register_combo("export_format", ["markdown"], self._settings["export"]["format"])); form.addRow("Auto Export", self._register_check("export_auto", self._settings["export"]["auto_export_after_analysis"])); return tab

    def _register_line(self, key: str, value: str, password: bool = False) -> QLineEdit:
        w = QLineEdit(value); 
        if password: w.setEchoMode(QLineEdit.EchoMode.Password)
        self._fields[key] = w; return w

    def _register_spin(self, key: str, value: int, mini: int, maxi: int) -> QSpinBox:
        w = QSpinBox(); w.setRange(mini, maxi); w.setValue(int(value)); self._fields[key] = w; return w

    def _register_dspin(self, key: str, value: float, mini: float, maxi: float, step: float) -> QDoubleSpinBox:
        w = QDoubleSpinBox(); w.setDecimals(2); w.setRange(mini, maxi); w.setSingleStep(step); w.setValue(float(value)); self._fields[key] = w; return w

    def _register_combo(self, key: str, options: list[str], value: str) -> QComboBox:
        w = QComboBox(); w.addItems(options); w.setCurrentText(value); self._fields[key] = w; return w

    def _register_check(self, key: str, value: bool) -> QCheckBox:
        w = QCheckBox(); w.setChecked(bool(value)); self._fields[key] = w; return w

    def _create_status_row(self, key: str) -> QWidget:
        row = QWidget(); layout = QHBoxLayout(row); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(8)
        indicator = QLabel(); indicator.setFixedSize(12, 12); indicator.setStyleSheet("background: #cbd5e1; border: 1px solid #94a3b8; border-radius: 6px;")
        text = QLabel("Not checked"); text.setWordWrap(True); self._api_status_widgets[key] = (indicator, text); layout.addWidget(indicator); layout.addWidget(text, 1); return row

    def _on_detect_gopro(self) -> None:
        self._stop_gopro_detection()
        self._announce_device_feedback("Scanning for GoPro (RNDIS)... please wait.")
        self._gopro_detection_thread = QThread(self); self._gopro_detection_worker = _GoProDetectionWorker(); self._gopro_detection_worker.moveToThread(self._gopro_detection_thread)
        self._gopro_detection_thread.started.connect(self._gopro_detection_worker.run); self._gopro_detection_worker.finished.connect(self._on_gopro_detection_finished); self._gopro_detection_worker.finished.connect(self._gopro_detection_thread.quit)
        self._gopro_detection_thread.finished.connect(self._gopro_detection_worker.deleteLater); self._gopro_detection_thread.finished.connect(self._gopro_detection_thread.deleteLater); self._gopro_detection_thread.finished.connect(self._stop_gopro_detection)
        self._gopro_detection_thread.start()

    def _stop_gopro_detection(self) -> None:
        try:
            if self._gopro_detection_thread and self._gopro_detection_thread.isRunning(): 
                self._gopro_detection_thread.quit(); self._gopro_detection_thread.wait(500)
        except RuntimeError: pass
        self._gopro_detection_thread = None; self._gopro_detection_worker = None

    def _on_gopro_detection_finished(self, result: dict[str, Any]) -> None:
        if bool(result.get("ok")):
            url = str(result.get("url", "")); self._line("custom_url").setText(url); self._announce_device_feedback(f"Success! {result.get('message')}")
            QMessageBox.information(self, "GoPro Detected", f"A GoPro was found:\n\n{url}")
        else:
            self._announce_device_feedback(f"Detection failed: {result.get('message')}")
            QMessageBox.warning(self, "GoPro Detection", str(result.get("message")))

    def _connect_api_key_live_checks(self) -> None:
        for k in ["api_openai", "api_replicate", "api_openrouter"]: self._line(k).textChanged.connect(self._schedule_api_validation)

    def _schedule_api_validation(self) -> None: self._api_validation_timer.start()

    def _validate_api_statuses(self) -> None:
        self._stop_api_validation_thread()
        self._api_validation_request_seq += 1
        payload = {"openai": self._line("api_openai").text().strip(), "replicate": self._line("api_replicate").text().strip(), "openrouter": self._line("api_openrouter").text().strip()}
        thread = QThread(self); worker = _ApiValidationWorker(self._api_validation_request_seq, payload); worker.moveToThread(thread)
        thread.started.connect(worker.run); worker.finished.connect(self._on_api_validation_worker_finished); worker.failed.connect(self._on_api_validation_worker_failed); thread.finished.connect(thread.deleteLater); thread.finished.connect(worker.deleteLater); thread.finished.connect(self._stop_api_validation_thread); thread.start()
        self._api_validation_thread = thread

    def _stop_api_validation_thread(self) -> None:
        try:
            if self._api_validation_thread and self._api_validation_thread.isRunning(): self._api_validation_thread.quit(); self._api_validation_thread.wait(500)
        except RuntimeError: pass
        self._api_validation_thread = None

    def _on_api_validation_worker_finished(self, request_id: int, result: object) -> None:
        if request_id == self._api_validation_request_seq and isinstance(result, dict): self._apply_api_validation_result(result)

    def _on_api_validation_worker_failed(self, request_id: int, error_text: str) -> None:
        if request_id == self._api_validation_request_seq: self._set_status("model_status", "error", f"Error: {error_text}")

    def _apply_api_validation_result(self, result: dict[str, Any]) -> None:
        services = result.get("services", {})
        for key in ("openai_status", "replicate_status", "openrouter_status"):
            data = services.get(key, {}); self._set_status(key, str(data.get("state", "idle")), str(data.get("text", "Not checked")))
        model_data = result.get("model_status", {}); self._set_status("model_status", str(model_data.get("state", "idle")), str(model_data.get("text", "Not checked")))
        self._refresh_analysis_provider_options()

    def _set_status(self, key: str, state: str, text: str) -> None:
        indicator, label = self._api_status_widgets[key]
        palette = {"ok": ("#16a34a", "#15803d"), "warn": ("#eab308", "#ca8a04"), "error": ("#ef4444", "#dc2626"), "checking": ("#3b82f6", "#2563eb"), "idle": ("#cbd5e1", "#94a3b8")}
        fill, border = palette.get(state, palette["idle"]); indicator.setStyleSheet(f"background: {fill}; border: 1px solid {border}; border-radius: 6px;"); label.setText(text)

    def _apply_settings_mode(self, mode_text: str) -> None:
        visible_tabs = {"Quick Start", "API Keys", "Webcam & Audio", "Viewport", "AI Analysis", "Cost", "Export"}
        is_adv = mode_text == "Advanced"
        for i in range(self.tab_widget.count()):
            name = self.tab_widget.tabText(i); visible = is_adv or name in visible_tabs
            if hasattr(self.tab_widget, "setTabVisible"): self.tab_widget.setTabVisible(i, visible)
        if not is_adv and self.tab_widget.tabText(self.tab_widget.currentIndex()) not in visible_tabs: self.tab_widget.setCurrentIndex(0)

    def _apply_field_tooltips(self) -> None:
        tips = HelpSystem.get_context_tooltips("settings_fields")
        for k, t in tips.items():
            if k in self._fields and hasattr(self._fields[k], "setToolTip"): self._fields[k].setToolTip(t)

    def _refresh_analysis_provider_options(self) -> None:
        available = []
        if self._line("api_replicate").text().strip(): available.append("replicate")
        if self._line("api_openrouter").text().strip(): available.append("openrouter")
        for k in ("analysis_provider", "quick_analysis_provider"):
            if k in self._fields:
                cb = self._combo(k); prev = cb.currentText(); cb.clear(); cb.addItems(available)
                if prev in available: cb.setCurrentText(prev)
        self._update_quick_start_summary()

    def _refresh_media_device_labels(self, *_args: object) -> None:
        c_labels = self._device_labels("camera"); m_labels = self._device_labels("mic")
        self._populate_device_selector(self._camera_device_combo, c_labels, "camera")
        self._populate_device_selector(self._mic_device_combo, m_labels, "microphone")
        self._sync_device_selectors_from_indices()
        self._camera_name_label.setText(self._device_label_text("camera", self._spin("camera_index").value()))
        self._mic_name_label.setText(self._device_label_text("mic", self._spin("mic_index").value()))

    def _device_label_text(self, device_type: str, index: int) -> str:
        labels = self._device_labels(device_type)
        if not labels: return "Names unavailable"
        return f"Detected: {labels[index]} ({index})" if 0 <= index < len(labels) else f"Index {index} not found"

    def _device_labels(self, device_type: str) -> list[str]:
        if QMediaDevices is None: return []
        try:
            devs = QMediaDevices.videoInputs() if device_type == "camera" else QMediaDevices.audioInputs()
            return [str(d.description()) for d in devs]
        except: return []

    def _populate_device_selector(self, combo: QComboBox | None, labels: list[str], label: str) -> None:
        if combo is None: return
        prev = combo.currentData(); combo.blockSignals(True); combo.clear()
        if labels:
            for idx, l in enumerate(labels): combo.addItem(f"{idx}: {l}", idx)
            if prev is not None:
                m_idx = combo.findData(prev)
                if m_idx >= 0: combo.setCurrentIndex(m_idx)
        else:
            combo.addItem(f"No {label} detected", -1); combo.setEnabled(False)
        combo.blockSignals(False)

    def _sync_device_selectors_from_indices(self, *_args: object) -> None:
        self._sync_device_selector(self._camera_device_combo, self._spin("camera_index").value())
        self._sync_device_selector(self._mic_device_combo, self._spin("mic_index").value())

    def _sync_device_selector(self, combo: QComboBox | None, val: int) -> None:
        if combo and combo.isEnabled():
            m_idx = combo.findData(val)
            if m_idx >= 0 and combo.currentIndex() != m_idx: combo.blockSignals(True); combo.setCurrentIndex(m_idx); combo.blockSignals(False)

    def _on_camera_device_selected(self, idx: int) -> None:
        if self._camera_device_combo and idx >= 0:
            dev_idx = self._camera_device_combo.itemData(idx)
            if isinstance(dev_idx, int) and dev_idx >= 0: self._spin("camera_index").setValue(dev_idx); self._camera_probe_timer.start()

    def _on_mic_device_selected(self, idx: int) -> None:
        if self._mic_device_combo and idx >= 0:
            dev_idx = self._mic_device_combo.itemData(idx)
            if isinstance(dev_idx, int) and dev_idx >= 0: self._spin("mic_index").setValue(dev_idx); self._audio_probe_timer.start()

    def _refresh_camera_preview_pipeline(self) -> None:
        c_idx = self._spin("camera_index").value(); c_url = self._line("custom_url").text().strip(); key = c_url if c_url else str(c_idx)
        if key in self._camera_resolution_cache:
            self._apply_camera_resolution_options(self._camera_resolution_cache[key])
            res = self._combo("webcam_resolution").currentText() or "1080p"
            self._camera_preview_monitor.start(c_idx, res, c_url)
        else:
            self._probe_camera_resolution_options(c_idx, c_url)

    def _probe_camera_resolution_options(self, camera_index: int, custom_url: str = "") -> None:
        if self._camera_resolution_probe_active: return
        self._camera_resolution_probe_active = True; self._camera_preview_monitor.stop(); self._stop_camera_probe()
        self._camera_probe_thread = QThread(self); self._camera_probe_worker = _CameraResolutionWorker(camera_index, custom_url); self._camera_probe_worker.moveToThread(self._camera_probe_thread)
        self._camera_probe_thread.started.connect(self._camera_probe_worker.run); self._camera_probe_worker.finished.connect(self._on_camera_probe_finished); self._camera_probe_worker.finished.connect(self._camera_probe_thread.quit)
        self._camera_probe_thread.finished.connect(self._camera_probe_worker.deleteLater); self._camera_probe_thread.finished.connect(self._camera_probe_thread.deleteLater); self._camera_probe_thread.finished.connect(self._stop_camera_probe); self._camera_probe_thread.start()

    def _stop_camera_probe(self) -> None:
        try:
            if self._camera_probe_thread and self._camera_probe_thread.isRunning(): self._camera_probe_thread.quit(); self._camera_probe_thread.wait(500)
        except RuntimeError: pass
        self._camera_probe_thread = None; self._camera_probe_worker = None; self._camera_resolution_probe_active = False

    def _on_camera_probe_finished(self, camera_index: int, options: list[str], message: str) -> None:
        c_url = self._line("custom_url").text().strip(); key = c_url if c_url else str(camera_index)
        self._camera_resolution_cache[key] = options; self._apply_camera_resolution_options(options, message)
        if int(self._spin("camera_index").value()) == camera_index:
            res = self._combo("webcam_resolution").currentText() or "1080p"; self._camera_preview_monitor.start(camera_index, res, c_url)

    def _apply_camera_resolution_options(self, options: list[str], msg: str = "") -> None:
        cb = self._combo("webcam_resolution"); prev = cb.currentText(); cb.blockSignals(True); cb.clear(); cb.addItems(options)
        if prev in options: cb.setCurrentText(prev)
        elif options: cb.setCurrentIndex(0)
        cb.blockSignals(False)
        if self._resolution_info_label: self._resolution_info_label.setText(msg or "Resolutions loaded.")

    def _restart_audio_monitor(self) -> None: self._audio_level_monitor.start(int(self._spin("mic_index").value()))

    def _refresh_live_device_feedback(self) -> None:
        f = self._camera_preview_monitor.get_last_frame()
        if f is not None: self._set_camera_preview_from_frame(f)
        elif self._camera_preview_label and self._camera_preview_pixmap is None:
            err = self._camera_preview_monitor.get_last_error()
            if err: self._camera_preview_label.setText(f"Camera Preview\n{err}")
        level = self._audio_level_monitor.get_level()
        if self._audio_level_bar: self._audio_level_bar.setValue(int(level * 100))
        if self._audio_feedback_label:
            status = "live" if self._audio_level_monitor.is_running() else "idle"
            self._audio_feedback_label.setText(f"Audio monitor: {status}, level {int(level * 100)}%")

    def _announce_device_feedback(self, text: str) -> None:
        if self._audio_feedback_label: self._audio_feedback_label.setText(text); self._device_feedback_timer.start()

    def _clear_device_feedback_hint(self) -> None: pass

    def _set_camera_preview_from_frame(self, frame: object) -> bool:
        if self._camera_preview_label is None or frame is None or not hasattr(frame, "shape"): return False
        try:
            rgb = frame[:, :, ::-1] # type: ignore
            image = QImage(rgb.data, int(rgb.shape[1]), int(rgb.shape[0]), int(rgb.strides[0]), QImage.Format.Format_RGB888).copy()
            pixmap = QPixmap.fromImage(image); self._camera_preview_pixmap = pixmap
            scaled = pixmap.scaled(self._camera_preview_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self._camera_preview_label.setText(""); self._camera_preview_label.setPixmap(scaled); return True
        except: return False

    def _on_test_webcam_device(self) -> None:
        c_idx = int(self._spin("camera_index").value()); c_url = self._line("custom_url").text().strip(); res = self._combo("webcam_resolution").currentText()
        self._announce_device_feedback("Testing webcam... please wait.")
        live = self._camera_preview_monitor.get_last_frame()
        if live is not None: self._set_camera_preview_from_frame(live); QMessageBox.information(self, "Webcam Test", "Live preview is working correctly.")
        else:
            result = Recorder.capture_single_frame(c_idx, str(res), timeout_seconds=2.0, custom_url=c_url)
            if bool(result.get("ok")): self._set_camera_preview_from_frame(result.get("frame")); QMessageBox.information(self, "Webcam Test", f"Success! {result.get('message')}")
            else: QMessageBox.warning(self, "Webcam Test", f"Failed: {result.get('message')}")

    def _on_test_audio_device(self) -> None:
        m_idx = int(self._spin("mic_index").value()); res = Recorder.sample_audio_input_level(m_idx); QMessageBox.information(self, "Audio Test", str(res.get("message")))

    def _apply_tab_tooltips(self) -> None:
        for i in range(self.tab_widget.count()): self.tab_widget.tabBar().setTabToolTip(i, HelpSystem.get_tooltip("settings_tabs", self.tab_widget.tabText(i)))

    def _add_tab_help_buttons(self) -> None:
        bar = self.tab_widget.tabBar()
        for i in range(self.tab_widget.count()):
            btn = QPushButton("?")
            btn.setFixedSize(22, 22)
            btn.clicked.connect(lambda _=False, name=self.tab_widget.tabText(i): HelpSystem.show_help_dialog(f"settings.tab.{name}", self))
            bar.setTabButton(i, QTabBar.ButtonPosition.RightSide, btn)

    def _sync_quick_start_into_fields(self) -> None:
        for k in ["viewport_mode", "analysis_provider", "analysis_model"]:
            if f"quick_{k}" in self._fields: self._combo(k).setCurrentText(self._combo(f"quick_{k}").currentText())

    def _sync_quick_start_from_fields(self) -> None:
        for k in ["viewport_mode", "analysis_provider", "analysis_model"]:
            if f"quick_{k}" in self._fields: self._combo(f"quick_{k}").setCurrentText(self._combo(k).currentText())

    def _apply_selected_preset(self) -> None:
        preset = self._combo("quick_preset").currentText()
        if preset == "Fast & Cheap":
            self._combo("analysis_provider").setCurrentText("openrouter"); self._combo("analysis_model").setCurrentText("qwen_vl")
        elif preset == "High Accuracy":
            self._combo("analysis_provider").setCurrentText("openrouter"); self._combo("analysis_model").setCurrentText("gpt4o_vision")
        self._sync_quick_start_from_fields()

    def _on_test_connections(self) -> None: self._schedule_api_validation()
    def _on_run_preflight(self) -> None:
        self._apply_into_state()
        if self._project_dir: PreflightDialog(self._project_dir, self._settings, self).exec()
    def _update_quick_start_summary(self) -> None:
        if self._quick_summary_label: self._quick_summary_label.setText(f"Project: {self._project_dir or 'None'}")

    def _line(self, k: str) -> QLineEdit: return self._fields[k] # type: ignore
    def _spin(self, k: str) -> QSpinBox: return self._fields[k] # type: ignore
    def _dspin(self, k: str) -> QDoubleSpinBox: return self._fields[k] # type: ignore
    def _combo(self, k: str) -> QComboBox: return self._fields[k] # type: ignore
    def _check(self, k: str) -> QCheckBox: return self._fields[k] # type: ignore
    def _plain(self, k: str) -> QPlainTextEdit: return self._fields[k] # type: ignore
