# -*- coding: utf-8 -*-
"""Local model wrappers (phase 2 placeholders)."""

from __future__ import annotations

from typing import Any


class LocalModels:
    """Placeholder wrappers for local OCR and gesture models."""

    def ocr(self, image: Any, languages: list[str] | None = None) -> list[dict[str, Any]]:
        del image, languages
        return []

    def detect_hands(self, frame: Any) -> list[dict[str, Any]]:
        del frame
        return []

    def get_fingertip_position(self, hand_landmarks: Any) -> tuple[int, int]:
        del hand_landmarks
        return (0, 0)

    def transcribe_local(self, audio_path, language: str = "de") -> dict[str, Any]:
        del audio_path, language
        return {"text": "", "segments": [], "provider": "whisper_local"}

