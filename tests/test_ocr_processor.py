# -*- coding: utf-8 -*-
"""Tests for OCR processor functionality."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from screenreview.pipeline.ocr_processor import OcrProcessor


class TestOcrProcessor:
    """Test OCR processor functionality."""

    def test_init(self):
        """Test OCR processor initialization."""
        processor = OcrProcessor()
        assert processor is not None
        assert hasattr(processor, 'ocr_engine')

    def test_get_ocr_context_no_data(self, tmp_path):
        """Test OCR context when no data exists."""
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

        import json
        ocr_file.write_text(json.dumps(ocr_data, ensure_ascii=False))

        processor = OcrProcessor()
        context = processor.get_ocr_context_for_prompt(tmp_path)

        assert "OCR Text Elements:" in context
        assert '"Test Button" at (150, 225)' in context

    def test_find_text_at_position(self, tmp_path):
        """Test finding text near a position."""
        # Create mock OCR data
        extraction_dir = tmp_path / ".extraction"
        extraction_dir.mkdir()
        ocr_file = extraction_dir / "screenshot_ocr.json"

        ocr_data = [
            {
                "text": "Button 1",
                "bbox": {
                    "top_left": {"x": 100, "y": 200},
                    "bottom_right": {"x": 200, "y": 250}
                },
                "confidence": 0.95
            },
            {
                "text": "Button 2",
                "bbox": {
                    "top_left": {"x": 300, "y": 400},
                    "bottom_right": {"x": 400, "y": 450}
                },
                "confidence": 0.90
            }
        ]

        import json
        ocr_file.write_text(json.dumps(ocr_data, ensure_ascii=False))

        processor = OcrProcessor()

        # Test finding text at center of first button
        matches = processor.find_text_at_position(tmp_path, 150, 225, tolerance=10)
        assert len(matches) == 1
        assert matches[0]["text"] == "Button 1"

        # Test finding text at center of second button
        matches = processor.find_text_at_position(tmp_path, 350, 425, tolerance=10)
        assert len(matches) == 1
        assert matches[0]["text"] == "Button 2"

        # Test no match
        matches = processor.find_text_at_position(tmp_path, 500, 500, tolerance=10)
        assert len(matches) == 0

    @patch('screenreview.pipeline.ocr_processor.OcrEngine')
    def test_process_route_screenshots(self, mock_ocr_engine_class, tmp_path):
        """Test processing multiple routes."""
        # Mock OCR engine
        mock_engine = Mock()
        mock_engine.extract_text.return_value = [
            {"text": "Test", "bbox": [0, 0, 10, 10], "confidence": 0.9}
        ]
        mock_ocr_engine_class.return_value = mock_engine

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

    @patch('screenreview.pipeline.ocr_processor.OcrEngine')
    def test_process_gesture_region(self, mock_ocr_engine_class, tmp_path):
        """Test gesture region OCR processing."""
        pytest.importorskip("PIL", reason="PIL/Pillow not available")

        # Mock OCR engine
        mock_engine = Mock()
        mock_engine.extract_text.return_value = [
            {"text": "Gesture Text", "bbox": [0, 0, 50, 50], "confidence": 0.85}
        ]
        mock_ocr_engine_class.return_value = mock_engine

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
            assert results[0]["bbox"][0] == 300  # 400 - 100
            assert results[0]["bbox"][1] == 200  # 300 - 100
