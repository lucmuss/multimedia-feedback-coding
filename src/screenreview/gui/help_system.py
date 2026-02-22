# -*- coding: utf-8 -*-
"""Centralized tooltip and contextual help texts for the GUI."""

from __future__ import annotations

from typing import Any

from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QPlainTextEdit, QVBoxLayout, QWidget


class HelpSystem:
    """Small centralized registry for tooltips and help topics."""

    _TOOLTIPS: dict[str, dict[str, str]] = {
        "main_window": {
            "viewer_widget": "Main screen preview area for the currently selected route screenshot.",
            "metadata_widget": "Technical metadata for the current screen (route, viewport, git info).",
            "batch_overview_widget": (
                "Overview of all screens in the session. Select a card to jump to that screen."
            ),
            "status_label": "Shows current screen index and processing state.",
            "route_label": "Shows the route path for the current screen.",
            "transcript_live_widget": "Live transcript and review notes captured during recording.",
            "progress_widget": "Pipeline progress for queued/processed review tasks.",
            "setup_status_widget": "Quick readiness summary for files, keys, and analysis configuration.",
            "batch_button": "Move keyboard focus to the batch overview panel for quick navigation.",
            "open_folder_button": "Open the current screen folder in the system file explorer.",
            "preflight_button": "Run a consolidated readiness check (files, disk, API keys, models).",
            "settings_button": "Open settings and API validation tools.",
        },
        "settings_tabs": {
            "Quick Start": "Recommended startup flow and common presets for faster setup.",
            "API Keys": "Configure API keys and validate service/model access in the background.",
            "Webcam & Audio": "Local recording input device and resolution settings.",
            "Viewport": "Select which route viewport folders are scanned (mobile or desktop).",
            "Speech-to-Text": "Configure the transcription backend and language hint.",
            "Frame Extraction": "Control frame sampling frequency and frame count limits.",
            "Gesture & OCR": "Local helpers for gesture detection and OCR extraction.",
            "AI Analysis": "Vision model provider and model alias used for analysis.",
            "Cost": "Budget caps and warnings for session spending.",
            "Hotkeys": "Keyboard shortcuts used in the review workflow.",
            "Export": "Result export format and auto-export behavior.",
        },
        "settings_fields": {
            "api_openai": "OpenAI API key for GPT-4o Transcribe and optional GPT-4o model checks.",
            "api_replicate": "Replicate API key for vision analysis models (currently optional fallback).",
            "api_openrouter": (
                "OpenRouter API key for alternate vision models when Replicate is unavailable."
            ),
            "camera_index": "Webcam device index. Use 0 for the default camera.",
            "mic_index": "Microphone input device index. Use 0 for the default microphone.",
            "webcam_resolution": (
                "Capture resolution for webcam recording. Higher resolution uses more storage."
            ),
            "viewport_mode": "Filters scanned route folders to mobile or desktop.",
            "stt_provider": "Speech-to-text provider for audio transcription.",
            "stt_language": "Language hint for transcription (for example de or en).",
            "frame_interval": "Lower values extract more frames and increase processing cost.",
            "frame_max": "Maximum frames kept per screen after extraction/selection.",
            "smart_enabled": "Smart Selector keeps fewer relevant frames to reduce API cost.",
            "gesture_enabled": "Enable local gesture detection for pointer/hand highlighting.",
            "ocr_enabled": "Enable local OCR to extract text from selected frames.",
            "gesture_sensitivity": (
                "Higher sensitivity may detect more gestures but can add false positives."
            ),
            "analysis_provider": (
                "Vision analysis backend. OpenRouter is recommended while Replicate is blocked."
            ),
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
        },
    }

    _TOPICS: dict[str, dict[str, Any]] = {
        "settings.tab.Quick Start": {
            "title": "Quick Start Help",
            "summary": "Use this tab for the fastest setup path before a review session.",
            "sections": [
                ("Project Folder", "The current routes directory used for scanning and preflight checks."),
                ("Preset", "Applies a curated bundle of settings for speed, quality, or local-first usage."),
                (
                    "Startup Flow",
                    "Enter API keys, choose provider/model, run preflight, then start the review session.",
                ),
            ],
        },
        "settings.tab.API Keys": {
            "title": "API Keys Help",
            "summary": "Configure external AI services and verify availability with short background checks.",
            "sections": [
                ("Live Checks", "Key edits trigger debounced validation updates in the background."),
                ("Test Connections", "Verifies key acceptance and basic network connectivity."),
                ("Test Models", "Checks whether the configured model aliases are available."),
            ],
        },
        "settings.tab.Webcam & Audio": {
            "title": "Webcam & Audio Help",
            "summary": "Configure local recording inputs used during review capture.",
            "sections": [
                ("Camera Index", "Use 0 for the default camera, then increase for other devices."),
                ("Microphone Index", "Use the OS device index for the desired audio input."),
                ("Resolution", "Higher resolution improves visibility but increases file size."),
            ],
        },
        "settings.tab.Viewport": {
            "title": "Viewport Help",
            "summary": "Controls which route folders are included during project scanning.",
            "sections": [
                ("mobile", "Loads only `*/mobile/` route captures."),
                ("desktop", "Loads only `*/desktop/` route captures."),
            ],
        },
        "settings.tab.Speech-to-Text": {
            "title": "Speech-to-Text Help",
            "summary": "Configure how audio is transcribed into review notes.",
            "sections": [
                ("Provider", "Choose cloud or local transcription backends."),
                ("Language", "A hint for transcription accuracy, such as `de` or `en`."),
            ],
        },
        "settings.tab.Frame Extraction": {
            "title": "Frame Extraction Help",
            "summary": "Controls how many video frames are extracted before analysis.",
            "sections": [
                ("Interval", "Lower interval extracts more frames and increases cost/processing."),
                ("Max Frames", "Hard cap for frames retained per screen."),
                ("Smart Selector", "Keeps fewer relevant frames to reduce analysis cost."),
            ],
        },
        "settings.tab.Gesture & OCR": {
            "title": "Gesture & OCR Help",
            "summary": "Optional local helpers for better frame selection and annotation context.",
            "sections": [
                ("Gesture Detection", "Highlights pointer or hand movement in recordings."),
                ("OCR", "Extracts visible text from selected frames."),
                ("Sensitivity", "Higher values detect more gestures but may add false positives."),
            ],
        },
        "settings.tab.AI Analysis": {
            "title": "AI Analysis Help",
            "summary": "Configures the multimodal vision backend for screen analysis.",
            "sections": [
                ("Provider", "Replicate or OpenRouter backend used for inference."),
                ("Model", "Model alias used by the analysis pipeline."),
                ("Tradeoff", "Use faster models for iteration and stronger models for final QA passes."),
            ],
        },
        "settings.tab.Cost": {
            "title": "Cost Help",
            "summary": "Budget settings for session-level spend monitoring.",
            "sections": [
                ("Budget Limit", "Hard cap for expected session spending."),
                ("Warning", "Early warning threshold before the budget limit is reached."),
                ("Auto Stop", "Stops analysis automatically when the budget limit is exceeded."),
            ],
        },
        "settings.tab.Hotkeys": {
            "title": "Hotkeys Help",
            "summary": "One mapping per line in the format `action: shortcut`.",
            "sections": [
                ("Examples", "next: Right, back: Left, record: R"),
                ("Tip", "Use Apply to save changes without closing the dialog."),
            ],
        },
        "settings.tab.Export": {
            "title": "Export Help",
            "summary": "Controls export format and automatic export after analysis.",
            "sections": [
                ("Format", "Choose markdown or json output."),
                ("Auto Export", "Writes results automatically after processing completes."),
            ],
        },
    }

    @classmethod
    def get_tooltip(cls, context: str, element: str, default: str = "No help available.") -> str:
        """Return a tooltip string for a UI context and element key."""
        return cls._TOOLTIPS.get(context, {}).get(element, default)

    @classmethod
    def get_context_tooltips(cls, context: str) -> dict[str, str]:
        """Return a copy of all tooltip entries for a context."""
        return dict(cls._TOOLTIPS.get(context, {}))

    @classmethod
    def get_topic(cls, context: str) -> dict[str, Any] | None:
        """Return a help topic definition by context id."""
        topic = cls._TOPICS.get(context)
        return dict(topic) if topic is not None else None

    @classmethod
    def build_help_dialog(cls, context: str, parent: QWidget | None = None) -> QDialog:
        """Create a modal help dialog for a given context."""
        topic = cls._TOPICS.get(context)
        dialog = QDialog(parent)
        dialog.setModal(True)

        if topic is None:
            dialog.setWindowTitle("Help")
            layout = QVBoxLayout(dialog)
            label = QLabel("No help is available for this context yet.")
            label.setWordWrap(True)
            layout.addWidget(label)
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
            buttons.rejected.connect(dialog.reject)
            buttons.accepted.connect(dialog.accept)
            buttons.button(QDialogButtonBox.StandardButton.Close).clicked.connect(dialog.close)
            layout.addWidget(buttons)
            return dialog

        dialog.setWindowTitle(str(topic.get("title", "Help")))
        dialog.resize(480, 320)
        layout = QVBoxLayout(dialog)

        summary_label = QLabel(str(topic.get("summary", "")))
        summary_label.setWordWrap(True)
        layout.addWidget(summary_label)

        sections = topic.get("sections", [])
        details = QPlainTextEdit()
        details.setReadOnly(True)
        text_lines: list[str] = []
        for title, content in sections:
            text_lines.append(f"{title}\n  {content}")
        details.setPlainText("\n\n".join(text_lines).strip())
        layout.addWidget(details, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        buttons.button(QDialogButtonBox.StandardButton.Close).clicked.connect(dialog.close)
        layout.addWidget(buttons)
        return dialog

    @classmethod
    def show_help_dialog(cls, context: str, parent: QWidget | None = None) -> int:
        """Build and execute a modal help dialog."""
        dialog = cls.build_help_dialog(context, parent=parent)
        return dialog.exec()
