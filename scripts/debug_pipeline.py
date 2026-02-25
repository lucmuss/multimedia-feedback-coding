#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Debug Pipeline - Test frame extraction and gesture detection step by step.
"""

from pathlib import Path
import json
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from screenreview.pipeline.frame_extractor import FrameExtractor
from screenreview.pipeline.gesture_detector import GestureDetector
from screenreview.pipeline.ocr_processor import OcrProcessor

def main():
    print("=== DEBUG PIPELINE ===\n")

    # Use the test data path provided by user
    screen_dir = Path("/mnt/o/projects/freya-online-dating/output/feedback/routes/login_html/desktop")
    extraction_dir = screen_dir / ".extraction"
    
    print(f"Screen directory: {screen_dir}")
    print(f"Extraction directory: {extraction_dir}\n")

    # Check what files exist
    print("📋 Checking existing files...")
    raw_video = extraction_dir / "raw_video.avi"
    raw_audio = extraction_dir / "raw_audio.wav"
    frames_dir = extraction_dir / "frames"
    gesture_regions_dir = extraction_dir / "gesture_regions"
    analysis_json = extraction_dir / "analysis.json"

    print(f"  ✓ raw_video.avi exists: {raw_video.exists()} ({raw_video.stat().st_size if raw_video.exists() else 0} bytes)")
    print(f"  ✓ raw_audio.wav exists: {raw_audio.exists()} ({raw_audio.stat().st_size if raw_audio.exists() else 0} bytes)")
    print(f"  ✓ frames/ exists: {frames_dir.exists()}")
    print(f"  ✓ gesture_regions/ exists: {gesture_regions_dir.exists()}")
    print(f"  ✓ analysis.json exists: {analysis_json.exists()} ({analysis_json.stat().st_size if analysis_json.exists() else 0} bytes)\n")

    # Check analysis.json content
    if analysis_json.exists():
        try:
            content = json.loads(analysis_json.read_text())
            print(f"  📄 analysis.json content: {content}\n")
        except:
            print(f"  📄 analysis.json is malformed\n")

    # Step 1: Frame Extraction
    print("=" * 50)
    print("STEP 1: Frame Extraction")
    print("=" * 50)

    if not raw_video.exists():
        print(f"❌ ERROR: raw_video.avi not found at {raw_video}")
        return

    print(f"🎬 Input video: {raw_video}")
    print(f"   Size: {raw_video.stat().st_size} bytes")

    # Get video info first
    frame_extractor = FrameExtractor(fps=1.0)  # 1 frame per second
    video_info = frame_extractor.get_video_info(raw_video)
    print(f"\n📊 Video Info:")
    print(f"   Duration: {video_info.get('duration', '?')} seconds")
    print(f"   Resolution: {video_info.get('width', '?')}x{video_info.get('height', '?')}")
    print(f"   FPS: {video_info.get('fps', '?')}")
    print(f"   Codec: {video_info.get('codec', '?')}")

    # Extract frames
    print(f"\n🔄 Extracting frames at 1 FPS into: {frames_dir}")
    frames = frame_extractor.extract_frames(raw_video, frames_dir)
    print(f"✅ Frame extraction complete: {len(frames)} frames extracted\n")

    if not frames:
        print("❌ ERROR: No frames extracted! Stopping here.\n")
        return

    for i, frame in enumerate(frames[:3]):
        print(f"   - {frame.name} ({frame.stat().st_size} bytes)")
    if len(frames) > 3:
        print(f"   ... and {len(frames) - 3} more frames")

    # Step 2: Gesture Detection
    print("\n" + "=" * 50)
    print("STEP 2: Gesture Detection")
    print("=" * 50)

    print(f"🎭 Detecting gestures in {len(frames)} frames...")
    gesture_detector = GestureDetector()
    
    # Process each frame
    gesture_events = []
    for i, frame_path in enumerate(frames[:5]):  # Test on first 5 frames
        print(f"   Processing frame {i+1}/{min(5, len(frames))}: {frame_path.name}")
        try:
            landmarks = gesture_detector.detect_landmarks(frame_path)
            if landmarks:
                gesture_events.append({
                    "frame_index": i,
                    "frame_path": str(frame_path),
                    "landmarks_count": len(landmarks),
                })
                print(f"      ✓ Found {len(landmarks)} landmarks")
            else:
                print(f"      - No landmarks detected")
        except Exception as e:
            print(f"      ❌ Error: {e}")

    print(f"\n✅ Gesture detection complete: {len(gesture_events)} gestures found\n")

    # Step 3: OCR Processing
    print("=" * 50)
    print("STEP 3: OCR Processing")
    print("=" * 50)

    print(f"📝 Running OCR on {len(frames[:3])} sample frames...")
    ocr_processor = OcrProcessor()
    
    ocr_results = []
    for i, frame_path in enumerate(frames[:3]):
        print(f"   Processing frame {i+1}: {frame_path.name}")
        try:
            ocr_text = ocr_processor.extract_text(frame_path)
            if ocr_text:
                ocr_results.append({
                    "frame_index": i,
                    "frame_path": str(frame_path),
                    "text": ocr_text[:100] + ("..." if len(ocr_text) > 100 else ""),
                })
                print(f"      ✓ OCR: {ocr_text[:50]}...")
            else:
                print(f"      - No text detected")
        except Exception as e:
            print(f"      ❌ Error: {e}")

    print(f"\n✅ OCR processing complete: {len(ocr_results)} frames with text\n")

    # Summary
    print("=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print(f"✓ Frames extracted: {len(frames)}")
    print(f"✓ Gestures detected: {len(gesture_events)}")
    print(f"✓ OCR results: {len(ocr_results)}")
    print("\n✅ Pipeline debugging complete!")
    print(f"\nFrames directory: {frames_dir}")
    print(f"Total frames: {len(list(frames_dir.glob('frame_*.png')))}")
    

if __name__ == "__main__":
    main()
