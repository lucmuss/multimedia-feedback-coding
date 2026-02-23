#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Complete gesture + OCR workflow example.

This script demonstrates the complete pipeline:
1. Load gesture events from video tracking
2. Process OCR on gesture regions
3. Match with transcript segments
4. Generate annotations
5. Write to transcript.md
"""

from pathlib import Path
from screenreview.pipeline.gesture_detector import GestureDetector
from screenreview.pipeline.ocr_processor import OcrProcessor


def main():
    """Run the complete gesture + OCR workflow."""
    print("=== ScreenReview Gesture + OCR Workflow ===\n")

    # Example data - in real usage this would come from actual video processing
    example_gesture_events = [
        {
            "timestamp": 5.2,
            "frame_index": 156,
            "webcam_position": {"x": 320, "y": 240},
            "screenshot_position": {"x": 195, "y": 420}
        },
        {
            "timestamp": 12.8,
            "frame_index": 384,
            "webcam_position": {"x": 280, "y": 200},
            "screenshot_position": {"x": 150, "y": 350}
        },
        {
            "timestamp": 20.1,
            "frame_index": 603,
            "webcam_position": {"x": 400, "y": 180},
            "screenshot_position": {"x": 280, "y": 80}
        }
    ]

    example_transcript_segments = [
        {
            "start": 3.0,
            "end": 8.0,
            "text": "Der Anmelden-Button muss entfernt werden"
        },
        {
            "start": 10.0,
            "end": 15.0,
            "text": "Das Passwort-Feld soll größer sein"
        },
        {
            "start": 18.0,
            "end": 22.0,
            "text": "Der Header passt so"
        }
    ]

    # For demo purposes, we'll use the existing screenshot structure
    # In real usage, you'd process actual video files
    project_dir = Path("output/feedback")
    routes_dir = project_dir / "routes"

    if not routes_dir.exists():
        print(f"Routes directory not found: {routes_dir}")
        print("Please run the main application first to generate screenshots.")
        return

    # Find a screenshot to work with
    example_screenshot = None
    example_meta = None
    for route_dir in routes_dir.iterdir():
        if not route_dir.is_dir():
            continue
        for viewport in ['mobile', 'desktop']:
            viewport_dir = route_dir / viewport
            screenshot = viewport_dir / "screenshot.png"
            meta_file = viewport_dir / "meta.json"
            if screenshot.exists() and meta_file.exists():
                example_screenshot = screenshot
                example_meta = meta_file
                break
        if example_screenshot:
            break

    if not example_screenshot or not example_meta:
        print("No suitable screenshot found for demo.")
        return

    print("1. Loading meta data...")
    import json
    meta = json.loads(example_meta.read_text())
    print(f"   Route: {meta.get('route', '?')}")
    print(f"   Viewport: {meta.get('viewport', '?')}")
    print(f"   Size: {meta.get('viewport_size', {}).get('w', '?')}x{meta.get('viewport_size', {}).get('h', '?')}")
    print()

    print("2. Initializing processors...")
    gesture_detector = GestureDetector()
    ocr_processor = OcrProcessor(engine="auto", languages=["de", "en"])
    print("   ✓ Gesture detector and OCR processor ready\n")

    print("3. Processing gesture annotations...")
    screen_dir = example_screenshot.parent
    annotations = ocr_processor.process_gesture_annotations(
        screen_dir, example_gesture_events, example_transcript_segments
    )
    print(f"   ✓ Created {len(annotations)} annotations\n")

    print("4. Annotation results:")
    trigger_icons = {
        "bug": "🔴 BUG",
        "ok": "✅ OK",
        "remove": "🔴 REMOVE",
        "resize": "🟡 RESIZE",
        "move": "🟡 MOVE",
        "restyle": "🟡 RESTYLE",
        "high_priority": "🔴 WICHTIG",
        None: "📝"
    }

    for ann in annotations:
        icon = trigger_icons.get(ann["trigger_type"], "📝")
        time_str = f"{int(ann['timestamp']//60):02d}:{int(ann['timestamp']%60):02d}"
        ocr = ann.get("ocr_text", "?")
        spoken = ann.get("spoken_text", "")
        x, y = ann["position"]["x"], ann["position"]["y"]

        print(f"   [{time_str}] {icon}: \"{spoken}\"")
        print(f"     → Position: ({x}, {y}) | OCR: \"{ocr}\"")
        print(f"     → Region: {ann.get('region_image', '')}")
        print()

    print("5. Writing to transcript.md...")
    write_annotations_to_transcript(
        screen_dir / "transcript.md",
        meta,
        annotations
    )
    print("   ✓ Transcript updated\n")

    print("=== Workflow Complete ===")
    print("\nGesture annotations are now available in:")
    print("- .extraction/gesture_annotations.json")
    print("- .extraction/gesture_regions/region_*.png")
    print("- transcript.md (updated)")


def write_annotations_to_transcript(
    transcript_path: Path,
    meta: dict,
    annotations: list[dict]
) -> None:
    """Write annotations to transcript.md format."""
    trigger_icons = {
        "bug": "🔴 BUG",
        "ok": "✅ OK",
        "remove": "🔴 REMOVE",
        "resize": "🟡 RESIZE",
        "move": "🟡 MOVE",
        "restyle": "🟡 RESTYLE",
        "high_priority": "🔴 WICHTIG",
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

    # Notes Section
    lines.append("## Notes")
    if not annotations:
        lines.append("- (keine Annotationen)")
    else:
        for ann in annotations:
            icon = trigger_icons.get(ann["trigger_type"], "📝")
            time_str = f"{int(ann['timestamp']//60):02d}:{int(ann['timestamp']%60):02d}"
            ocr = ann.get("ocr_text", "?")
            spoken = ann.get("spoken_text", "")
            x = ann["position"]["x"]
            y = ann["position"]["y"]

            lines.append(
                f"- [{time_str}] {icon}: \"{spoken}\""
            )
            lines.append(
                f"  → Position: ({x}, {y}) | "
                f"OCR: \"{ocr}\" | "
                f"Region: {ann.get('region_image', '')}"
            )
    lines.append("")

    # Numbered Refs
    lines.append("## Numbered refs (optional)")
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