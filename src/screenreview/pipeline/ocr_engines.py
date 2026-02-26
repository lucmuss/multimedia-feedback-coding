# -*- coding: utf-8 -*-
"""Modular OCR engines - Abstract base and concrete implementations."""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class BaseOcrEngine(ABC):
    """Abstract base class for OCR engines."""

    def __init__(self, languages: list[str] | None = None) -> None:
        self.languages = languages or ["de", "en"]
        self.is_available = False
        self._init_engine()

    @abstractmethod
    def _init_engine(self) -> None:
        """Initialize the OCR engine. Set self.is_available."""
        pass

    @abstractmethod
    def extract_from_image(self, image_path: Path) -> list[dict[str, Any]]:
        """Extract text from image file.
        
        Returns list of dicts with keys: text, bbox, confidence
        bbox format: [x1, y1, x2, y2]
        """
        pass

    def extract_text(self, image: Any) -> list[dict[str, Any]]:
        """Generic extraction method handling different input types."""
        if isinstance(image, Path):
            return self.extract_from_image(image)
        elif isinstance(image, str):
            return self.extract_from_image(Path(image))
        elif isinstance(image, dict):
            # Handle pre-extracted sidecar data
            texts = image.get("texts", [])
            if isinstance(texts, list):
                return [self._normalize_entry(entry, i) for i, entry in enumerate(texts)]
        elif isinstance(image, (bytes, bytearray)):
            # Fallback for binary data
            decoded = bytes(image).decode("utf-8", errors="ignore")
            if "TEXT:" in decoded:
                text = decoded.split("TEXT:", 1)[1].strip() or ""
                return [self._make_entry(text=text, bbox=[0, 0, 10, 10], confidence=0.9)]
        
        return []

    def _normalize_entry(self, entry: Any, default_index: int) -> dict[str, Any]:
        """Normalize OCR entry to standard format."""
        if isinstance(entry, dict):
            return self._make_entry(
                text=str(entry.get("text", "")),
                bbox=list(entry.get("bbox", [0, default_index * 10, 10, 10])),
                confidence=float(entry.get("confidence", 0.8)),
            )
        return self._make_entry(text=str(entry), bbox=[0, default_index * 10, 10, 10], confidence=0.8)

    def _make_entry(self, text: str, bbox: list[int], confidence: float) -> dict[str, Any]:
        """Create standard OCR entry."""
        return {"text": text, "bbox": bbox, "confidence": confidence}

    def get_name(self) -> str:
        """Get engine name."""
        return self.__class__.__name__


class EasyOcrEngine(BaseOcrEngine):
    """EasyOCR engine implementation."""

    def _init_engine(self) -> None:
        """Initialize EasyOCR."""
        try:
            import easyocr
            self._reader = easyocr.Reader(self.languages, gpu=False)
            self.is_available = True
            logger.info(f"✓ EasyOCR initialized with languages: {self.languages}")
        except (ImportError, OSError, Exception) as e:
            logger.warning(f"EasyOCR not available: {e}")
            self._reader = None
            self.is_available = False

    def extract_from_image(self, image_path: Path) -> list[dict[str, Any]]:
        """Extract text using EasyOCR."""
        if not self.is_available or self._reader is None:
            logger.warning("EasyOCR not available")
            return []

        if not image_path.exists():
            logger.warning(f"Image not found: {image_path}")
            return []

        try:
            logger.debug(f"Extracting text from {image_path.name} using EasyOCR...")
            results = self._reader.readtext(str(image_path))
            
            entries = []
            for detection in results:
                bbox, text, confidence = detection
                # Convert bbox points to [x1, y1, x2, y2]
                x_coords = [int(point[0]) for point in bbox]
                y_coords = [int(point[1]) for point in bbox]
                bbox_int = [min(x_coords), min(y_coords), max(x_coords), max(y_coords)]
                
                entries.append(self._make_entry(text, bbox_int, float(confidence)))
            
            logger.debug(f"EasyOCR found {len(entries)} text regions in {image_path.name}")
            return entries
        except Exception as e:
            logger.error(f"EasyOCR extraction failed: {e}")
            return []


class PaddleOcrEngine(BaseOcrEngine):
    """PaddleOCR engine implementation."""

    def _init_engine(self) -> None:
        """Initialize PaddleOCR."""
        try:
            from paddleocr import PaddleOCR
            # Initialize with specified languages
            supported_langs = []
            for lang in self.languages:
                if lang == "de":
                    supported_langs.append("german")
                elif lang == "en":
                    supported_langs.append("en")
                else:
                    supported_langs.append(lang)
            
            self._ocr = PaddleOCR(use_angle_cls=True, lang=supported_langs if supported_langs else ["en"])
            self.is_available = True
            logger.info(f"✓ PaddleOCR initialized with languages: {supported_langs}")
        except (ImportError, Exception) as e:
            logger.warning(f"PaddleOCR not available: {e}")
            self._ocr = None
            self.is_available = False

    def extract_from_image(self, image_path: Path) -> list[dict[str, Any]]:
        """Extract text using PaddleOCR."""
        if not self.is_available or self._ocr is None:
            logger.warning("PaddleOCR not available")
            return []

        if not image_path.exists():
            logger.warning(f"Image not found: {image_path}")
            return []

        try:
            logger.debug(f"Extracting text from {image_path.name} using PaddleOCR...")
            results = self._ocr.ocr(str(image_path), cls=True)
            
            entries = []
            for line in results:
                if line is None:
                    continue
                for detection in line:
                    bbox, (text, confidence) = detection
                    # Convert bbox points to [x1, y1, x2, y2]
                    x_coords = [int(point[0]) for point in bbox]
                    y_coords = [int(point[1]) for point in bbox]
                    bbox_int = [min(x_coords), min(y_coords), max(x_coords), max(y_coords)]
                    
                    entries.append(self._make_entry(text, bbox_int, float(confidence)))
            
            logger.debug(f"PaddleOCR found {len(entries)} text regions in {image_path.name}")
            return entries
        except Exception as e:
            logger.error(f"PaddleOCR extraction failed: {e}")
            return []


class TesseractOcrEngine(BaseOcrEngine):
    """Tesseract OCR engine implementation (pytesseract Python wrapper)."""

    def _init_engine(self) -> None:
        """Initialize Tesseract OCR via pytesseract."""
        try:
            import pytesseract
            from PIL import Image
            self._pytesseract = pytesseract
            self._image_lib = Image
            
            # Map standard language codes to tesseract codes
            self.tesseract_langs = []
            for lang in self.languages:
                if lang == "de":
                    self.tesseract_langs.append("deu")
                elif lang == "en":
                    self.tesseract_langs.append("eng")
                else:
                    self.tesseract_langs.append(lang)

            # Test if tesseract binary is available
            self._pytesseract.get_tesseract_version()
            self.is_available = True
            logger.info(f"✓ Tesseract OCR initialized with languages: {self.tesseract_langs}")
        except Exception as e:
            logger.warning(f"Tesseract OCR not available: {e}. Install with: pip install pytesseract")
            self._pytesseract = None
            self.is_available = False

    def extract_from_image(self, image_path: Path) -> list[dict[str, Any]]:
        """Extract text using Tesseract OCR."""
        if not self.is_available or self._pytesseract is None:
            logger.warning("Tesseract OCR not available")
            return []

        if not image_path.exists():
            logger.warning(f"Image not found: {image_path}")
            return []

        try:
            logger.debug(f"Extracting text from {image_path.name} using Tesseract...")
            image = self._image_lib.open(image_path)
            
            # Get detailed OCR data with bounding boxes
            lang_str = '+'.join(self.tesseract_langs)
            data = self._pytesseract.image_to_data(
                image, lang=lang_str, output_type=self._pytesseract.Output.DICT
            )
            
            entries = []
            n_boxes = len(data['level'])
            for i in range(n_boxes):
               if int(data['conf'][i]) > 0:
                    text = data['text'][i].strip()
                    if not text:
                        continue
                    
                    x1 = int(data['left'][i])
                    y1 = int(data['top'][i])
                    x2 = x1 + int(data['width'][i])
                    y2 = y1 + int(data['height'][i])
                    confidence = int(data['conf'][i]) / 100.0
                    
                    entries.append(self._make_entry(text, [x1, y1, x2, y2], confidence))
            
            logger.debug(f"Tesseract found {len(entries)} text regions in {image_path.name}")
            return entries
        except Exception as e:
            logger.error(f"Tesseract extraction failed: {e}")
            return []


import threading

class OcrEngineFactory:
    """Factory for creating OCR engine instances."""

    _available_cache: list[str] | None = None
    _probe_lock = threading.Lock()

    @staticmethod
    def get_available_engines() -> list[str]:
        """Get list of available OCR engines. Gracefully handles import failures."""
        # 1. Fast path: return cache if already probed
        if OcrEngineFactory._available_cache is not None:
            return OcrEngineFactory._available_cache
            
        # 2. Avoid blocking if another thread (like the background probe) is already working.
        # This prevents the GUI from freezing if settings are opened during startup.
        if not OcrEngineFactory._probe_lock.acquire(blocking=False):
            logger.debug("OCR engine probe is already running in background. Returning empty list for now.")
            return []
            
        try:
            # Re-check cache inside lock
            if OcrEngineFactory._available_cache is not None:
                return OcrEngineFactory._available_cache
                
            available = []
            logger.info("Probing available OCR engines (this may take a few seconds on first run)...")
            
            try:
                import easyocr  # noqa: F401
                available.append("easyocr")
            except (ImportError, OSError, Exception) as e:
                logger.debug(f"EasyOCR not available: {type(e).__name__}: {e}")
            
            try:
                from paddleocr import PaddleOCR  # noqa: F401
                available.append("paddleocr")
            except (ImportError, OSError, Exception) as e:
                logger.debug(f"PaddleOCR not available: {type(e).__name__}: {e}")
            
            OcrEngineFactory._available_cache = available
            return available
        finally:
            OcrEngineFactory._probe_lock.release()

    @staticmethod
    def create_engine(engine_name: str = "auto", languages: list[str] | None = None) -> BaseOcrEngine | None:
        """Create OCR engine instance.
        
        Args:
            engine_name: "auto", "tesseract", "easyocr", or "paddleocr"
            languages: List of language codes (e.g., ["de", "en"])
            
        Returns:
            OCR engine instance or None if not available
        """
        languages = languages or ["de", "en"]
        
        if engine_name == "tesseract":
            engine = TesseractOcrEngine(languages)
            if engine.is_available:
                return engine
            logger.warning("Tesseract OCR not available")
            return None
        
        elif engine_name == "easyocr":
            engine = EasyOcrEngine(languages)
            if engine.is_available:
                return engine
            logger.warning("EasyOCR not available")
            return None
        
        elif engine_name == "paddleocr":
            engine = PaddleOcrEngine(languages)
            if engine.is_available:
                return engine
            logger.warning("PaddleOCR not available")
            return None
        
        elif engine_name == "auto":
            # Try available engines in priority order (Tesseract -> EasyOCR -> PaddleOCR)
            for engine_type in [TesseractOcrEngine, EasyOcrEngine, PaddleOcrEngine]:
                engine = engine_type(languages)
                if engine.is_available:
                    logger.info(f"Using {engine.get_name()} for OCR")
                    return engine
            
            logger.error("No OCR engine available. Install one: pip install pytesseract")
            return None
        
        logger.error(f"Unknown OCR engine: {engine_name}")
        return None
