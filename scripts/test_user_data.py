#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run complete pipeline on specific user data."""

from pathlib import Path
import json
import sys

from screenreview.pipeline.frame_extractor import FrameExtractor
from screenreview.pipeline.gesture_detector import GestureDetector
from screenreview.pipeline.ocr_processor import OcrProcessor
from screenreview.pipeline.trigger_detector import TriggerDetector
from screenreview.pipeline.exporter import Exporter
from screenreview.pipeline.analyzer import Analyzer
from screenreview.models.extraction_result import ExtractionResult
from screenreview.models.screen_item import ScreenItem
from screenreview.pipeline.transcriber import Transcriber

def main():
    target_dir = Path("/mnt/o/projects/freya-online-dating/output/feedback/routes/login_password_reset_html/mobile")
    if not target_dir.exists():
        print(f"Directory not found: {target_dir}")
        return

    extraction_dir = target_dir / ".extraction"
    raw_video = extraction_dir / "raw_video.avi"
    raw_audio = extraction_dir / "raw_audio.wav"
    screenshot_path = target_dir / "screenshot.png"
    meta_path = target_dir / "meta.json"

    meta_data = {}
    if meta_path.exists():
        meta_data = json.loads(meta_path.read_text())

    print("1. Extracting frames...")
    frame_extractor = FrameExtractor(fps=1.0)
    frames_dir = extraction_dir / "frames"
    frame_paths = frame_extractor.extract_frames(raw_video, frames_dir)
    print(f"Extracted {len(frame_paths)} frames.")

    print("2. Detecting gestures...")
    gesture_detector = GestureDetector()
    gesture_events = []
    import cv2
    for i, fpath in enumerate(frame_paths):
        frame = cv2.imread(str(fpath))
        is_gest, x, y = gesture_detector.detect_gesture_in_frame(frame)
        if is_gest:
            gesture_events.append({
                "timestamp": i * 1.0,
                "frame_index": i,
                "webcam_position": {"x": x, "y": y},
                "screenshot_position": {"x": x, "y": y}
            })
    print(f"Detected {len(gesture_events)} gestures.")

    print("3. Transcribing audio...")
    # Using local mock or real whisper if available. For this test, we'll mock the transcription
    # unless OpenAI is configured. Let's use a mock for deterministic testing.
    mock_transcript = {
        "text": "Das ist ein Test für den Anmeldebildschirm. Hier ist ein Bug. Der Button ist zu klein.",
        "segments": [
            {"start": 1.0, "end": 4.0, "text": "Das ist ein Test für den Anmeldebildschirm."},
            {"start": 5.0, "end": 7.0, "text": "Hier ist ein Bug."},
            {"start": 8.0, "end": 10.0, "text": "Der Button ist zu klein."}
        ]
    }

    print("4. Detecting triggers...")
    trigger_detector = TriggerDetector()
    processed_segments = trigger_detector.process_transcript_segments(mock_transcript["segments"])
    trigger_events = []
    for seg in processed_segments:
        if seg.get("primary_trigger"):
            trigger_events.append({
                "time": seg["start"],
                "type": seg["primary_trigger"],
                "text": seg["text"]
            })

    print("5. OCR Processing & Annotations...")
    ocr_processor = OcrProcessor()
    annotations = ocr_processor.process_gesture_annotations(target_dir, gesture_events, mock_transcript["segments"])

    print("6. Creating Extraction Result...")
    screen_item = ScreenItem(
        name="login_password_reset_html",
        route=meta_data.get("route", "login"),
        viewport=meta_data.get("viewport", "mobile"),
        screenshot_path=screenshot_path,
        metadata_path=meta_path,
        extraction_dir=extraction_dir,
        viewport_size=meta_data.get("viewport_size", {"w": 390, "h": 844}),
        timestamp_utc=meta_data.get("timestamp_utc", ""),
        git_branch=meta_data.get("git", {}).get("branch", ""),
        git_commit=meta_data.get("git", {}).get("commit", ""),
        browser="chromium",
        transcript_path=target_dir / "transcript.md"
    )

    extraction = ExtractionResult(
        screen=screen_item,
        video_path=raw_video,
        audio_path=raw_audio,
        transcript_text=mock_transcript["text"],
        transcript_segments=mock_transcript["segments"],
        trigger_events=trigger_events,
        annotations=annotations,
        ocr_results=[],
        gesture_positions=gesture_events,
        selected_frames=frame_paths
    )

    print("7. Running AI Analyzer (Testing Analysis Flow)...")
    from screenreview.integrations.openrouter_client import OpenRouterClient
    openrouter_client = OpenRouterClient(api_key="test-mock-key")
    analyzer = Analyzer(openrouter_client=openrouter_client)
    analysis_result = analyzer.analyze(extraction, {
        "analysis": {"enabled": True, "provider": "openrouter", "model": "gpt4o_vision"},
        "api_keys": {"openrouter": "test-mock-key"}
    })

    print("8. Exporting...")
    exporter = Exporter(Transcriber())
    paths = exporter.export(extraction, metadata=meta_data, analysis_data={"summary": analysis_result.summary, "bugs": analysis_result.bugs})

    print("✅ Complete pipeline test successful.")
    print(f"Transcript exported to: {paths['transcript']}")

if __name__ == "__main__":
    main()
