# -*- coding: utf-8 -*-
"""Gesture detection using MediaPipe."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class GestureDetector:
    """Detect pointing gestures in video frames."""

    def __init__(self) -> None:
        self._mp_hands = None
        self._hands = None
        self._init_mediapipe()

    def _init_mediapipe(self) -> None:
        """Initialize MediaPipe Hands."""
        try:
            import mediapipe as mp
            
            # Robust import for different MediaPipe versions
            if hasattr(mp, "solutions") and hasattr(mp.solutions, "hands"):
                self._mp_hands = mp.solutions.hands
                self._mp_drawing = mp.solutions.drawing_utils
            else:
                try:
                    import mediapipe.python.solutions.hands as mp_hands
                    import mediapipe.python.solutions.drawing_utils as mp_drawing
                    self._mp_hands = mp_hands
                    self._mp_drawing = mp_drawing
                except ImportError:
                    # Try direct import from mediapipe.solutions
                    import mediapipe.solutions.hands as mp_hands
                    import mediapipe.solutions.drawing_utils as mp_drawing
                    self._mp_hands = mp_hands
                    self._mp_drawing = mp_drawing

            if self._mp_hands:
                self._hands = self._mp_hands.Hands(
                    static_image_mode=False,
                    max_num_hands=1,
                    min_detection_confidence=0.7,
                    min_tracking_confidence=0.5
                )
                logger.info("MediaPipe Hands initialized successfully")
            else:
                raise AttributeError("MediaPipe solutions.hands not found")
                
        except (ImportError, AttributeError, Exception) as e:
            logger.warning(f"MediaPipe not available or failed to initialize: {e}. Install with: pip install mediapipe")
            self._hands = None

    def detect_gesture_in_frame(self, frame: Any, optimize: bool = True) -> tuple[bool, int | None, int | None]:
        """Detect pointing gesture in a single frame."""
        if self._hands is None or frame is None:
            return False, None, None

        try:
            import cv2
            import numpy as np

            # Optional image optimization for better detection
            if optimize:
                frame = self._optimize_image_for_detection(frame)

            # Convert BGR to RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame_height, frame_width = frame.shape[:2]

            # Process frame
            result = self._hands.process(frame_rgb)

            if not result.multi_hand_landmarks:
                return False, None, None

            hand = result.multi_hand_landmarks[0]

            if self._is_pointing_gesture(hand):
                x, y = self._get_fingertip_position(hand, frame_width, frame_height)
                return True, x, y

        except Exception as e:
            logger.warning(f"Gesture detection failed: {e}")

        return False, None, None

    def _is_pointing_gesture(self, hand_landmarks) -> bool:
        """Check if hand is making a pointing gesture."""
        landmarks = hand_landmarks.landmark

        # Index finger extended (tip higher than middle joint)
        index_extended = landmarks[8].y < landmarks[6].y

        # Other fingers folded (tips lower than middle joints)
        middle_folded = landmarks[12].y > landmarks[10].y
        ring_folded = landmarks[16].y > landmarks[14].y
        pinky_folded = landmarks[20].y > landmarks[18].y

        return index_extended and middle_folded and ring_folded and pinky_folded

    def _get_fingertip_position(self, hand_landmarks, frame_width: int, frame_height: int) -> tuple[int, int]:
        """Get fingertip position in pixel coordinates."""
        tip = hand_landmarks.landmark[8]  # INDEX_FINGER_TIP

        x = int(tip.x * frame_width)
        y = int(tip.y * frame_height)

        return x, y

    def _optimize_image_for_detection(self, frame: Any) -> Any:
        """Apply contrast enhancement to improve detection in low light."""
        import cv2
        import numpy as np

        try:
            # Convert to LAB color space
            lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)

            # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            cl = clahe.apply(l)

            # Merge channels and convert back to BGR
            limg = cv2.merge((cl, a, b))
            enhanced = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
            return enhanced
        except Exception as e:
            logger.debug(f"Image optimization failed: {e}")
            return frame

    def map_webcam_to_screenshot(
        self,
        webcam_x: int,
        webcam_y: int,
        webcam_width: int,
        webcam_height: int,
        beamer_region: dict[str, int],
        screenshot_width: int,
        screenshot_height: int
    ) -> tuple[int, int]:
        """Map webcam coordinates to screenshot coordinates."""
        # Position relative to beamer region
        rel_x = webcam_x - beamer_region["x"]
        rel_y = webcam_y - beamer_region["y"]

        # Normalize to 0.0-1.0
        norm_x = rel_x / beamer_region["width"]
        norm_y = rel_y / beamer_region["height"]

        # Scale to screenshot coordinates
        screenshot_x = int(norm_x * screenshot_width)
        screenshot_y = int(norm_y * screenshot_height)

        # Clamp to bounds
        screenshot_x = max(0, min(screenshot_x, screenshot_width - 1))
        screenshot_y = max(0, min(screenshot_y, screenshot_height - 1))

        return screenshot_x, screenshot_y

    def track_gestures_in_video(
        self,
        video_path: str,
        beamer_region: dict[str, int],
        screenshot_width: int,
        screenshot_height: int
    ) -> list[dict[str, Any]]:
        """Track gestures throughout a video."""
        logger.info(f"[B3] Starting gesture tracking for video: {video_path}")
        logger.debug(f"[B3] Beamer region: {beamer_region}")
        logger.debug(f"[B3] Screenshot dimensions: {screenshot_width}x{screenshot_height}")

        if self._hands is None:
            logger.warning("[B3] MediaPipe not available, skipping gesture detection")
            return []

        try:
            import cv2

            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                logger.error(f"[B3] Could not open video: {video_path}")
                return []

            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            logger.info(f"[B3] Video opened: {total_frames} frames at {fps} FPS")

            gesture_events = []
            frame_index = 0

            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break

                is_gesture, wx, wy = self.detect_gesture_in_frame(frame)

                if is_gesture and wx is not None and wy is not None:
                    sx, sy = self.map_webcam_to_screenshot(
                        wx, wy,
                        int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                        int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                        beamer_region,
                        screenshot_width,
                        screenshot_height
                    )

                    timestamp = frame_index / fps if fps > 0 else frame_index

                    gesture_events.append({
                        "timestamp": round(timestamp, 2),
                        "frame_index": frame_index,
                        "webcam_position": {"x": wx, "y": wy},
                        "screenshot_position": {"x": sx, "y": sy}
                    })

                frame_index += 1

            cap.release()
            return gesture_events

        except Exception as e:
            logger.error(f"Gesture tracking failed: {e}")
            return []