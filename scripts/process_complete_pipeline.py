#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Complete ScreenReview pipeline: Audio + Video + OCR + Gestures + Transcripts.

This script implements the full pipeline without KI analysis:
1. Record audio/video
2. Extract frames
3. Detect gestures
4. Transcribe audio
5. Detect triggers
6. Generate transcript.md
"""

from pathlib import Path
from screenreview.pipeline.audio_recorder import AudioRecorder
from screenreview.pipeline.frame_extractor import FrameExtractor
from screenreview.pipeline.gesture_detector import GestureDetector
from screenreview.pipeline.ocr_processor import OcrProcessor
from screenreview.pipeline.trigger_detector import TriggerDetector


def main():
    """Run the complete ScreenReview pipeline."""
    print("=== ScreenReview Complete Pipeline ===\n")

    # Configuration
    project_dir = Path("output/feedback")
    routes_dir = project_dir / "routes"

    if not routes_dir.exists():
        print(f"Routes directory not found: {routes_dir}")
        print("Please run the main application first to generate screenshots.")
        return

    # Find a screen to process
    screen_dir = None
    meta_data = None

    for route_dir in routes_dir.iterdir():
        if not route_dir.is_dir():
            continue
        for viewport in ['mobile', 'desktop']:
            viewport_dir = route_dir / viewport
            screenshot = viewport_dir / "screenshot.png"
            meta_file = viewport_dir / "meta.json"
            if screenshot.exists() and meta_file.exists():
                screen_dir = viewport_dir
                import json
                meta_data = json.loads(meta_file.read_text())
                break
        if screen_dir:
            break

    if not screen_dir or not meta_data:
        print("No suitable screen found for processing.")
        return

    print(f"Processing screen: {meta_data.get('route', '?')} ({meta_data.get('viewport', '?')})")
    print(f"Size: {meta_data.get('viewport_size', {}).get('w', '?')}x{meta_data.get('viewport_size', {}).get('h', '?')}")
    print()

    # Initialize components
    print("1. Initializing components...")
    audio_recorder = AudioRecorder()
    frame_extractor = FrameExtractor(fps=1.0)  # 1 frame per second
    gesture_detector = GestureDetector()
    ocr_processor = OcrProcessor()
    trigger_detector = TriggerDetector()
    print("   ✓ All components ready\n")

    # For demo: simulate recorded files (in real usage these would be recorded)
    extraction_dir = screen_dir / ".extraction"
    extraction_dir.mkdir(exist_ok=True)

    # Mock data for demonstration
    mock_audio_path = extraction_dir / "raw_audio.wav"
    mock_video_path = extraction_dir / "raw_video.mp4"

    # Create mock audio file (empty for demo)
    if not mock_audio_path.exists():
        mock_audio_path.write_text("mock audio data")

    # Create mock video file (empty for demo)
    if not mock_video_path.exists():
        mock_video_path.write_text("mock video data")

    print("2. Frame extraction...")
    frames_dir = extraction_dir / "frames"
    frame_paths = frame_extractor.extract_frames(mock_video_path, frames_dir)
    print(f"   ✓ Extracted {len(frame_paths)} frames\n")

    print("3. Gesture detection...")
    # Mock gesture detection on frames
    gesture_events = []
    for i, frame_path in enumerate(frame_paths):
        # Simulate gesture detection (in real usage: actual MediaPipe processing)
        if i in [2, 5, 10]:  # Simulate gestures at certain frames
            gesture_events.append({
                "timestamp": i * 1.0,  # 1 second per frame
                "frame_index": i,
                "webcam_position": {"x": 320, "y": 240},
                "screenshot_position": {"x": 195, "y": 420 - i * 20}  # Vary Y position
            })

    print(f"   ✓ Detected {len(gesture_events)} gestures\n")

    print("4. Audio transcription...")
    # Mock transcription (in real usage: actual OpenAI API call)
    mock_transcript = {
        "text": "Der Anmelden-Button muss entfernt werden. Das Passwort-Feld soll größer sein. Der Header passt so.",
        "language": "de",
        "duration": 12.0,
        "segments": [
            {
                "start": 2.0,
                "end": 6.0,
                "text": "Der Anmelden-Button muss entfernt werden."
            },
            {
                "start": 7.0,
                "end": 11.0,
                "text": "Das Passwort-Feld soll größer sein."
            },
            {
                "start": 12.0,
                "end": 15.0,
                "text": "Der Header passt so."
            }
        ]
    }

    # Save transcription
    transcript_path = extraction_dir / "audio_transcription.json"
    import json
    transcript_path.write_text(json.dumps(mock_transcript, indent=2, ensure_ascii=False))

    print("   ✓ Transcribed audio\n")

    print("5. Trigger detection...")
    processed_segments = trigger_detector.process_transcript_segments(mock_transcript["segments"])

    # Save processed segments
    segments_path = extraction_dir / "audio_segments.json"
    segments_path.write_text(json.dumps(processed_segments, indent=2, ensure_ascii=False))

    trigger_summary = trigger_detector.get_trigger_summary(processed_segments)
    print(f"   ✓ Detected triggers: {trigger_summary}\n")

    print("6. Gesture annotations...")
    annotations = ocr_processor.process_gesture_annotations(
        screen_dir, gesture_events, mock_transcript["segments"]
    )
    print(f"   ✓ Created {len(annotations)} annotations\n")

    print("7. Generating transcript.md...")
    write_complete_transcript(
        screen_dir / "transcript.md",
        meta_data,
        mock_transcript,
        annotations
    )
    print("   ✓ Transcript written\n")

    print("=== Pipeline Complete ===")
    print("\nGenerated files:")
    print("- .extraction/audio_transcription.json")
    print("- .extraction/audio_segments.json")
    print("- .extraction/gesture_annotations.json")
    print("- .extraction/frames/frame_*.png")
    print("- .extraction/gesture_regions/region_*.png")
    print("- transcript.md (complete)")


def write_complete_transcript(
    transcript_path: Path,
    meta: dict,
    transcript: dict,
    annotations: list[dict]
) -> None:
    """Write complete transcript.md with all data."""
    trigger_icons = {
        "bug": "🔴 BUG",
        "ok": "✅ OK",
        "remove": "🔴 REMOVE",
        "resize": "🟡 RESIZE",
        "move": "🟡 MOVE",
        "restyle": "🟡 RESTYLE",
        "high_priority": "🔴 WICHTIG",
        "add": "🟢 ADD",
        "text": "📝 TEXT",
        "navigation": "🧭 NAV",
        None: "📝"
    }

    lines = []

    # Header from meta.json
    lines.append("# Transcript (Voice -> Text)")
    lines.append(f"Route: {meta.get('route', '?')}")
    lines.append(f"Viewport: {meta.get('viewport', '?')}")
    vs = meta.get("viewport_size", {})
    lines.append(f"Size: {vs.get('w', '?')}x{vs.get('h', '?')}")
    git = meta.get("git", {})
    lines.append(f"Branch: {git.get('branch', '?')}")
    lines.append(f"Commit: {git.get('commit', '?')}")
    lines.append(f"Timestamp: {meta.get('timestamp_utc', '?')}")
    lines.append("")

    # Audio transcription
    lines.append("## Audio-Transkription")
    lines.append(transcript.get("text", ""))
    lines.append("")

    # Annotations
    lines.append("## Annotationen")
    if not annotations:
        lines.append("- (keine Annotationen)")
    else:
        for ann in annotations:
            icon = trigger_icons.get(ann["trigger_type"], "📝")
            time_str = f"{int(ann['timestamp']//60):02d}:{int(ann['timestamp']%60):02d}"
            ocr = ann.get("ocr_text", "?")
            spoken = ann.get("spoken_text", "")
            x, y = ann["position"]["x"], ann["position"]["y"]

            lines.append(
                f"- [{time_str}] {icon}: \"{spoken}\""
            )
            lines.append(
                f"  → Position: ({x}, {y}) | OCR: \"{ocr}\""
            )
            lines.append(
                f"  → Region: {ann.get('region_image', '')}"
            )
    lines.append("")

    # Numbered refs
    lines.append("## Numbered refs")
    for i, ann in enumerate(annotations, 1):
        icon = trigger_icons.get(ann["trigger_type"], "📝")
        ocr = ann.get("ocr_text", "?")
        spoken = ann.get("spoken_text", "")
        lines.append(f"{i}: {icon} {ocr} – {spoken}")
    lines.append("")

    transcript_path.write_text(
        "\n".join(lines),
        encoding="utf-8"
    )


if __name__ == "__main__":
    main()