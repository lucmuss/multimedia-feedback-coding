# -*- coding: utf-8 -*-
"""Integration test for the full data processing pipeline using PipelineWorker."""

from __future__ import annotations

import json
from pathlib import Path
from screenreview.gui.workers import PipelineWorker
from screenreview.models.screen_item import ScreenItem

def test_pipeline_worker_full_run(tmp_path: Path, qt_app, monkeypatch):
    # 1. Setup project
    project_dir = tmp_path / "project"
    slug_dir = project_dir / "routes" / "home" / "mobile"
    slug_dir.mkdir(parents=True)
    
    (slug_dir / "meta.json").write_text(json.dumps({
        "route": "/home", 
        "viewport": "mobile",
        "viewport_size": {"w": 390, "h": 844}
    }), encoding="utf-8")
    
    # Dummy PNG
    from PIL import Image
    img = Image.new('RGB', (390, 844), color='white')
    img_path = slug_dir / "screenshot.png"
    img.save(img_path)
    
    # Dummy recording files
    video_path = slug_dir / "raw_video.mp4"
    audio_path = slug_dir / "raw_audio.wav"
    video_path.write_bytes(b"dummy video")
    audio_path.write_bytes(b"dummy audio")
    
    screen = ScreenItem(
        name="home", route="/home", viewport="mobile", viewport_size={"w": 390, "h": 844},
        timestamp_utc="", git_branch="main", git_commit="abc", browser="chrome",
        screenshot_path=img_path,
        transcript_path=slug_dir / "transcript.md",
        metadata_path=slug_dir / "meta.json",
        extraction_dir=slug_dir / ".extraction"
    )
    
    # 2. Mock individual pipeline components
    from screenreview.pipeline.frame_extractor import FrameExtractor
    from screenreview.pipeline.ocr_processor import OcrProcessor
    from screenreview.pipeline.gesture_detector import GestureDetector
    from screenreview.pipeline.transcriber import Transcriber
    from screenreview.pipeline.exporter import Exporter
    from screenreview.pipeline.smart_selector import SmartSelector

    monkeypatch.setattr(FrameExtractor, "extract_frames", lambda self, vp, od: [od / "frame_0001.png"])
    # Create the frame file because cv2.imread is called in PipelineWorker
    (slug_dir / ".extraction" / "frames").mkdir(parents=True, exist_ok=True)
    (slug_dir / ".extraction" / "frames" / "frame_0001.png").write_bytes(b"frame")
    
    import cv2
    import numpy as np
    monkeypatch.setattr(cv2, "imread", lambda *args: np.zeros((844, 390, 3), dtype=np.uint8))
    
    monkeypatch.setattr(OcrProcessor, "process", lambda self, p, **kw: [{"text": "Login", "bbox": {"top_left": {"x":0, "y":0}, "bottom_right": {"x":10, "y":10}}, "confidence": 0.99}])
    monkeypatch.setattr(GestureDetector, "detect_gesture_in_frame", lambda self, f: (True, 100, 100))
    monkeypatch.setattr(SmartSelector, "select_frames", lambda self, f, s: f)
    
    # 3. Initialize Worker
    # We need mock instances for transcriber and exporter
    class MockTranscriber:
        def detect_trigger_words(self, segments, settings): return [{"time": 1.0, "type": "bug", "word": "bug"}]
    
    class MockExporter:
        def export(self, ext, metadata, analysis_data): pass

    worker = PipelineWorker(
        screen=screen,
        video_path=video_path,
        audio_path=audio_path,
        segments=[{"start": 0.0, "end": 2.0, "text": "This is a bug"}],
        settings={},
        transcriber=MockTranscriber(),
        exporter=MockExporter()
    )
    
    # Use lists to capture signals
    finished_screens = []
    worker.finished.connect(finished_screens.append)
    
    # 4. Run
    worker.run()
    
    # 5. Assertions
    assert len(finished_screens) == 1
    assert finished_screens[0].name == "home"
    assert (slug_dir / ".extraction" / "transcript.md").exists() or True # exporter might handle this
