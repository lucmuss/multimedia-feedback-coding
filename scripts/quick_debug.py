#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Quick debug - just check the basic structure"""

from pathlib import Path
import json
import subprocess

def main():
    print("=== QUICK DEBUG ===\n")

    screen_dir = Path("/mnt/o/projects/freya-online-dating/output/feedback/routes/login_html/desktop")
    extraction_dir = screen_dir / ".extraction"
    
    raw_video = extraction_dir / "raw_video.avi"
    raw_audio = extraction_dir / "raw_audio.wav"
    frames_dir = extraction_dir / "frames"
    
    print(f"✓ Screen dir: {screen_dir.exists()}")
    print(f"✓ Extraction dir: {extraction_dir.exists()}")
    print(f"✓ Raw video: {raw_video.exists()} ({raw_video.stat().st_size} bytes)")
    print(f"✓ Raw audio: {raw_audio.exists()} ({raw_audio.stat().st_size} bytes)")
    print(f"✓ Frames dir: {frames_dir.exists()}\n")

    # Get video info using ffprobe
    print("Getting video info...")
    try:
        result = subprocess.run([
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", str(raw_video)
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            info = json.loads(result.stdout)
            if "streams" in info and info["streams"]:
                stream = info["streams"][0]
                print(f"✓ Video resolution: {stream.get('width')}x{stream.get('height')}")
                print(f"✓ FPS: {stream.get('r_frame_rate')}")
                print(f"✓ Codec: {stream.get('codec_name')}")
            if "format" in info:
                print(f"✓ Duration: {float(info['format'].get('duration', 0)):.1f}s\n")
    except Exception as e:
        print(f"❌ FFprobe failed: {e}\n")
        return

    # Try one frame extraction
    print("Attempting frame extraction...")
    test_dir = extraction_dir / "test_frames"
    test_dir.mkdir(exist_ok=True)
    
    cmd = [
        "ffmpeg",
        "-i", str(raw_video),
        "-vf", "fps=1",
        "-start_number", "1",
        "-q:v", "2",
        "-y",
        str(test_dir / "frame_%04d.png")
    ]
    
    print(f"Running: ffmpeg ... fps=1 ...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        frames = list(test_dir.glob("frame_*.png"))
        print(f"✓ Extracted {len(frames)} frames")
        
        if frames:
            first_frame = frames[0]
            print(f"✓ First frame: {first_frame.name} ({first_frame.stat().st_size} bytes)")
            
            # Show first 3 frames
            for i, f in enumerate(frames[:3]):
                print(f"  - {f.name}")
        else:
            print(f"❌ No frames extracted!")
            if result.stderr:
                print(f"FFmpeg stderr: {result.stderr[:500]}")
                
    except subprocess.TimeoutExpired:
        print("❌ Timeout during frame extraction")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
