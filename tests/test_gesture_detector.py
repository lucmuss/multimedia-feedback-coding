import numpy as np
import pytest
from screenreview.pipeline.gesture_detector import GestureDetector

def test_detect_gesture_init():
    detector = GestureDetector()
    assert detector is not None

def test_map_webcam_to_screenshot():
    detector = GestureDetector()
    # Mock beamer region at (100, 100) with size 200x200
    beamer = {"x": 100, "y": 100, "width": 200, "height": 200}
    
    # Point exactly in the middle of beamer (200, 200)
    sx, sy = detector.map_webcam_to_screenshot(
        200, 200, 640, 480, beamer, 1000, 1000
    )
    
    # Middle of beamer should be middle of screenshot
    assert sx == 500
    assert sy == 500

def test_map_webcam_to_screenshot_clamping():
    detector = GestureDetector()
    beamer = {"x": 100, "y": 100, "width": 200, "height": 200}
    
    # Point far outside beamer
    sx, sy = detector.map_webcam_to_screenshot(
        50, 50, 640, 480, beamer, 1000, 1000
    )
    
    assert sx == 0
    assert sy == 0

