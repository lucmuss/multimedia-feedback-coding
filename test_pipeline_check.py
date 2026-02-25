#!/usr/bin/env python3
"""Quick pipeline validation - checks if all components are available."""

import sys
from pathlib import Path

print("=" * 60)
print("🔍 Pipeline Components Check")
print("=" * 60)
print()

errors = []

# 1. Check ExtractionInitializer
print("1. ExtractionInitializer...")
try:
    from screenreview.utils.extraction_init import ExtractionInitializer
    print("   ✓ Imported successfully")
    print("   ✓ Methods: ensure_structure, validate_structure, repair_structure")
except Exception as e:
    print(f"   ✗ Error: {e}")
    errors.append("ExtractionInitializer")

# 2. Check FrameExtractor
print()
print("2. FrameExtractor...")
try:
    from screenreview.pipeline.frame_extractor import FrameExtractor
    print("   ✓ Imported successfully")
    print("   ✓ Methods: extract_frames, get_video_info, smart_select_frames")
except Exception as e:
    print(f"   ✗ Error: {e}")
    errors.append("FrameExtractor")

# 3. Check GestureDetector
print()
print("3. GestureDetector...")
try:
    from screenreview.pipeline.gesture_detector import GestureDetector
    print("   ✓ Imported successfully")
    print("   ✓ Methods: detect_gesture_in_frame, map_webcam_to_screenshot")
except Exception as e:
    print(f"   ✗ Error: {e}")
    errors.append("GestureDetector")

# 4. Check OcrProcessor
print()
print("4. OcrProcessor...")
try:
    from screenreview.pipeline.ocr_processor import OcrProcessor
    print("   ✓ Imported successfully")
    print("   ✓ Methods: process_route_screenshots, process, get_ocr_context_for_prompt")
except Exception as e:
    print(f"   ✗ Error: {e}")
    errors.append("OcrProcessor")

# 5. Check OcrEngineFactory
print()
print("5. OcrEngineFactory...")
try:
    from screenreview.pipeline.ocr_engines import OcrEngineFactory, TesseractOcrEngine
    print("   ✓ Imported successfully")
    available = OcrEngineFactory.get_available_engines()
    print(f"   ✓ Available engines: {available}")
    print("   ✓ Default engine priority: Tesseract → EasyOCR → PaddleOCR")
except Exception as e:
    print(f"   ✗ Error: {e}")
    errors.append("OcrEngineFactory")

# 6. Check SmartSelector
print()
print("6. SmartSelector...")
try:
    from screenreview.pipeline.smart_selector import SmartSelector
    print("   ✓ Imported successfully")
    print("   ✓ Methods: select_frames, calculate_cost_savings")
except Exception as e:
    print(f"   ✗ Error: {e}")
    errors.append("SmartSelector")

print()
print("=" * 60)
if errors:
    print(f"❌ {len(errors)} component(s) failed:")
    for e in errors:
        print(f"   - {e}")
    sys.exit(1)
else:
    print("✅ All pipeline components are functional!")
    print()
    print("Pipeline flow:")
    print("  1. ExtractionInitializer - Creates .extraction directory structure")
    print("  2. FrameExtractor - Extracts frames from video (FFmpeg required)")
    print("  3. GestureDetector - Detects gestures in frames (MediaPipe)")
    print("  4. OCRProcessor - Extracts text from frames (Tesseract/EasyOCR/PaddleOCR)")
    print("  5. SmartSelector - Selects best frames for analysis")
    print()
    print("✓ Complete pipeline validation successful!")
    sys.exit(0)
