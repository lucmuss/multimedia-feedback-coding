# -*- coding: utf-8 -*-
"""OCR engine with PaddleOCR and EasyOCR support."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from screenreview.utils.file_utils import write_json_file

logger = logging.getLogger(__name__)

try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False
    logger.warning("EasyOCR not available. Install with: pip install easyocr")


class OcrEngine:
    """OCR engine with PaddleOCR and EasyOCR support."""

    def __init__(self, languages: list[str] | None = None, engine: str = "auto") -> None:
        self.languages = languages or ["de", "en"]
        self.engine = engine  # "auto", "paddleocr", "easyocr"
        self._paddle_ocr = None
        self._easy_ocr = None
        self._init_engines()

    def _init_engines(self) -> None:
        """Initialize OCR engines."""
        if EASYOCR_AVAILABLE:
            try:
                # EasyOCR initialization
                self._easy_ocr = easyocr.Reader(self.languages)
                logger.info("EasyOCR initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize EasyOCR: {e}")
                self._easy_ocr = None

    def extract_text(self, image: Any) -> list[dict[str, Any]]:
        if isinstance(image, dict):
            texts = image.get("texts", [])
            if isinstance(texts, list):
                return [self._normalize_entry(entry, default_index=i) for i, entry in enumerate(texts)]
            return []

        if isinstance(image, (bytes, bytearray)):
            decoded = bytes(image).decode("utf-8", errors="ignore")
            if "TEXT:" in decoded:
                text = decoded.split("TEXT:", 1)[1].strip() or ""
                return [self._make_entry(text=text, bbox=[0, 0, 10, 10], confidence=0.9)]
            return []

        if isinstance(image, Path):
            return self._extract_from_path(image)

        return []

    def extract_from_region(self, image: Any, x: int, y: int, w: int, h: int) -> list[dict[str, Any]]:
        entries = self.extract_text(image)
        for entry in entries:
            entry["bbox"] = [x, y, w, h]
        return entries

    def process_frames(self, frame_paths: list[Path]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for frame_path in frame_paths:
            texts = self.extract_text(frame_path)
            payload = {"frame": frame_path.name, "texts": texts}
            results.append(payload)
            out_path = frame_path.with_name(frame_path.stem + "_ocr.json")
            write_json_file(out_path, payload)
        return results

    def _extract_from_path(self, image_path: Path) -> list[dict[str, Any]]:
        sidecar = image_path.with_suffix(image_path.suffix + ".ocr-source.json")
        if sidecar.exists():
            raw = json.loads(sidecar.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and isinstance(raw.get("texts"), list):
                return [self._normalize_entry(entry, default_index=i) for i, entry in enumerate(raw["texts"])]
            if isinstance(raw, list):
                return [self._normalize_entry(entry, default_index=i) for i, entry in enumerate(raw)]
            return []

        # Try real OCR if no sidecar file
        return self._perform_ocr(image_path)

    def _perform_ocr(self, image_path: Path) -> list[dict[str, Any]]:
        """Perform OCR using available engines."""
        if not image_path.exists():
            return []

        if self._easy_ocr is not None:
            try:
                results = self._easy_ocr.readtext(str(image_path))
                entries = []
                for bbox, text, confidence in results:
                    bbox_int = [int(coord) for coord in bbox[0] + bbox[2]]  # top-left and bottom-right
                    entries.append(self._make_entry(text, bbox_int, float(confidence)))
                if entries:
                    logger.debug(f"EasyOCR found {len(entries)} text regions in {image_path.name}")
                    return entries
            except Exception as e:
                logger.warning(f"EasyOCR failed for {image_path}: {e}")

        # Fallback: no OCR results
        logger.info(f"No OCR results for {image_path.name} - EasyOCR not available or failed")
        return []

    def _normalize_entry(self, entry: Any, default_index: int) -> dict[str, Any]:
        if isinstance(entry, dict):
            return self._make_entry(
                text=str(entry.get("text", "")),
                bbox=list(entry.get("bbox", [0, default_index * 10, 10, 10])),
                confidence=float(entry.get("confidence", 0.8)),
            )
        return self._make_entry(
            text=str(entry),
            bbox=[0, default_index * 10, 10, 10],
            confidence=0.8,
        )

    def _make_entry(self, text: str, bbox: list[int], confidence: float) -> dict[str, Any]:
        return {"text": text, "bbox": bbox, "confidence": confidence}

