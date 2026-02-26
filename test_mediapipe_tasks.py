import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import cv2
import numpy as np

try:
    print("Testing MediaPipe Tasks API...")
    # This usually requires a model file (.task)
    # Since I don't have it, I'll just check if the classes exist
    print(f"Vision: {vision}")
    print(f"HandLandmarker: {vision.HandLandmarker}")
    print("✓ Tasks API classes found")
except Exception as e:
    print(f"✗ Tasks API error: {e}")
