# -*- coding: utf-8 -*-
"""Tests for OCR processor functionality."""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from screenreview.pipeline.ocr_processor import OcrProcessor

class TestOcrProcessor:
    """Test OCR processor functionality."""

    def test_init(self):
        """Test OCR processor initialization."""
        with patch('screenreview.pipeline.ocr_engines.OcrEngineFactory.create_engine') as mock_create:
            mock_create.return_value = Mock()
            processor = OcrProcessor()
            assert processor is not None
            assert hasattr(processor, 'ocr_engine')

    def test_get_ocr_context_no_data(self, tmp_path):
        """Test OCR context when no data exists."""
        with patch('screenreview.pipeline.ocr_engines.OcrEngineFactory.create_engine') as mock_create:
            mock_create.return_value = Mock()
            processor = OcrProcessor()
            context = processor.get_ocr_context_for_prompt(tmp_path)
            assert "(No OCR data available)" in context

    def test_get_ocr_context_with_data(self, tmp_path):
        """Test OCR context with existing data."""
        # Create mock OCR data
        extraction_dir = tmp_path / ".extraction"
        extraction_dir.mkdir()
        ocr_file = extraction_dir / "screenshot_ocr.json"

        ocr_data = [
            {
                "text": "Test Button",
                "bbox": {
                    "top_left": {"x": 100, "y": 200},
                    "bottom_right": {"x": 200, "y": 250}
                },
                "confidence": 0.95
            }
        ]

        ocr_file.write_text(json.dumps(ocr_data, ensure_ascii=False))

        with patch('screenreview.pipeline.ocr_engines.OcrEngineFactory.create_engine') as mock_create:
            mock_create.return_value = Mock()
            processor = OcrProcessor()
            context = processor.get_ocr_context_for_prompt(tmp_path)

            assert "OCR Text Elements:" in context
            assert '"Test Button" at (150, 225)' in context

    @patch('screenreview.pipeline.ocr_engines.OcrEngineFactory.create_engine')
    def test_process_route_screenshots(self, mock_create, tmp_path):
        """Test processing multiple routes."""
        # Mock OCR engine
        mock_engine = Mock()
        mock_engine.extract_text.return_value = [
            {"text": "Test", "bbox": [0, 0, 10, 10], "confidence": 0.9}
        ]
        mock_create.return_value = mock_engine

        # Create test directory structure
        routes_dir = tmp_path / "routes"
        route_dir = routes_dir / "test_route"
        mobile_dir = route_dir / "mobile"
        mobile_dir.mkdir(parents=True)

        screenshot = mobile_dir / "screenshot.png"
        screenshot.write_text("fake png")

        processor = OcrProcessor()
        results = processor.process_route_screenshots(routes_dir)

        assert "test_route" in results
        assert "mobile" in results["test_route"]
        assert results["test_route"]["mobile"]["text_count"] == 1

    @patch('screenreview.pipeline.ocr_engines.OcrEngineFactory.create_engine')
    def test_process_gesture_region(self, mock_create, tmp_path):
        """Test gesture region OCR processing."""
        pytest.importorskip("PIL", reason="PIL/Pillow not available")

        # Mock OCR engine
        mock_engine = Mock()
        mock_engine.extract_text.return_value = [
            {"text": "Gesture Text", "bbox": [0, 0, 50, 50], "confidence": 0.85}
        ]
        mock_create.return_value = mock_engine

        # Mock PIL Image in the function
        with patch('PIL.Image.open') as mock_image_open:
            mock_image = Mock()
            mock_image.width = 800
            mock_image.height = 600
            mock_image.crop.return_value = mock_image
            mock_image_open.return_value = mock_image

            screenshot = tmp_path / "test.png"
            screenshot.write_text("fake")

            processor = OcrProcessor()
            results = processor.process_gesture_region(screenshot, 400, 300, region_size=100)

            assert len(results) == 1
            assert results[0]["text"] == "Gesture Text"
            # Check that bbox was adjusted back to original coordinates
            # bbox in mock is [0,0,50,50]. left=300, top=200.
            # adjusted bbox: [300, 200, 350, 250]
            assert results[0]["bbox"][0] == 300
            assert results[0]["bbox"][1] == 200
