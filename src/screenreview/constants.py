# -*- coding: utf-8 -*-
"""Application constants."""

APP_NAME = "multimedia-feedback-coding"
APP_VERSION = "0.1.0"

DEFAULT_SETTINGS_FILE = "settings.json"
DEFAULT_TRANSCRIPT_TEMPLATE = """# Transcript (Voice -> Text)
Route: {route}
Viewport: {viewport}

## Notes
- (add voice transcription here)

## Numbered refs (optional)
1:
2:
3:
"""

VIEWPORT_MODES = ("mobile", "desktop")

DEFAULT_HOTKEYS = {
    "next": "Ctrl+N",
    "skip": "Ctrl+K",
    "back": "Ctrl+B",
    "record": "Ctrl+R",
    "pause": "Ctrl+P",
    "stop": "Ctrl+S",
}

