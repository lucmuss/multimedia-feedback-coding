# AI Agent & Automation Guide

This document describes the tools and interfaces built into `multimedia-feedback-coding` to allow AI coding assistants and automation scripts to autonomously test, diagnose, and monitor the application.

## Core Documentation
For a deeper understanding of the system, AI agents should refer to:
- [**DATENFLUSS.md**](DATENFLUSS.md): Detailed explanation of how data moves from recording to analysis.
- [**PROJEKT_STATUS.md**](PROJEKT_STATUS.md): Current development progress, completed features, and roadmap.

## 1. System Diagnostics
If the application is behaving unexpectedly, AI agents should first run the diagnostic tool to identify environmental issues (missing dependencies, invalid API keys, disk space).

```bash
# Run the diagnostic tool
uv run python -m screenreview.diagnose
```

**Output:**
- **Console:** A human-readable summary.
- **File:** `logs/diagnostic_report.json` (Structured data for AI parsing).

## 2. Testing & Debugging Scripts
To verify system components or UI stability without manual interaction, use the following scripts.

### GUI Automation
Simulates clicks through settings, tabs, and recording actions to verify UI stability.
```bash
# Recommended for regression testing
uv run python scripts/run_gui_self_test.py
```

### Pipeline Debugging & Integration
Tests the internal processing components (Frame Extraction, Gesture Detection, OCR) in isolation or through a full integration run using mock data.
```bash
# Full Integration Test (Recommended)
uv run pytest tests/test_pipeline_integration.py -v

# Individual Unit Tests
uv run pytest tests/test_frame_extractor.py
uv run pytest tests/test_ocr_processor.py

# Debug script for real projects
uv run python scripts/debug_pipeline.py [project_path]
```

### Hardware Verification
Quickly checks if cameras and microphones are accessible to the system.
```bash
# Generic hardware check
uv run python scripts/test_hardware.py

# Detailed webcam/resolution check
uv run python scripts/test_webcams.py
```

AI agents can check the console output for `=== Completed Successfully ===` or similar success markers to verify a safe run.

## 3. Real-time GUI State Monitoring
The application periodically dumps its internal state to a JSON file while running. This allows an AI agent to "see" the current state of the app without access to a video stream.

- **Path:** `logs/gui_state_snapshot.json`
- **Updates:** Every 5 seconds.
- **Content:** Window title, active project, current screen index, recording status, and timestamps.

## 4. UI Automation (Widget Naming)
For tools like `PyQt6.QtTest` or accessibility-based automation, key widgets have fixed `objectName` properties:

| Widget / Button | Object Name |
| :--- | :--- |
| **Record Button** | `blueButton` (idle) / `dangerButton` (active) |
| **Next Button** | `greenButton` |
| **Settings Action** | `settingsAction` |
| **Test Webcam Button** | `testWebcamBtn` |
| **Test Audio Button** | `testAudioBtn` |
| **Run Preflight Button**| `runPreflightBtn` |
| **Apply Preset Button** | `applyPresetBtn` |
| **API Status Indicators**| `openai_status`, `replicate_status`, etc. |

## 5. Development Logs
The application always runs in **DEBUG** mode by default (unless configured otherwise).
- **Session Logs:** Located in `logs/multimedia-feedback-coding-YYYYMMDD-HHMMSS.log`.
- **Traceability:** Logs include thread names (e.g., `[MainThread]`, `[QThread]`) to help debug asynchronous freezes or race conditions.
