# -*- coding: utf-8 -*-
"""Worker classes for asynchronous background processing."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal

from screenreview.models.extraction_result import ExtractionResult
from screenreview.models.screen_item import ScreenItem
from screenreview.pipeline.annotation_analyzer import AnnotationAnalyzer
from screenreview.pipeline.exporter import Exporter
from screenreview.pipeline.frame_extractor import FrameExtractor
from screenreview.pipeline.gesture_detector import GestureDetector
from screenreview.pipeline.ocr_processor import OcrProcessor
from screenreview.pipeline.smart_selector import SmartSelector
from screenreview.pipeline.transcriber import Transcriber

logger = logging.getLogger(__name__)


class TranscriptionWorker(QObject):
    """Asynchronous worker for STT via API."""
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, transcriber: Transcriber, audio_path: Path, provider: str, language: str) -> None:
        super().__init__()
        self.transcriber = transcriber
        self.audio_path = audio_path
        self.provider = provider
        self.language = language

    def run(self) -> None:
        try:
            logger.info("TranscriptionWorker: Starting STT (%s, %s)", self.provider, self.language)
            result = self.transcriber.transcribe(self.audio_path, provider=self.provider, language=self.language)
            segments = result.get("segments", [])
            if not segments:
                segments = [{"start": 0.0, "end": 1.0, "text": "(No API speech results)"}]
            self.finished.emit(segments)
        except Exception as e:
            logger.exception("TranscriptionWorker: STT API failed")
            self.error.emit(str(e))


class PipelineWorker(QObject):
    """
    Asynchronous worker for the full analysis pipeline 
    (Frames -> Gestures -> OCR -> Annotations -> Export).
    """
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(ScreenItem)
    error = pyqtSignal(str)

    def __init__(
        self,
        screen: ScreenItem,
        video_path: Path,
        audio_path: Path,
        segments: list[dict[str, Any]],
        settings: dict[str, Any],
        transcriber: Transcriber,
        exporter: Exporter,
    ) -> None:
        super().__init__()
        self.screen = screen
        self.video_path = video_path
        self.audio_path = audio_path
        self.segments = segments
        self.settings = settings
        self.transcriber = transcriber
        self.exporter = exporter

    def run(self) -> None:
        try:
            from screenreview.utils.extraction_init import ExtractionInitializer
            import cv2
            
            # 1. Structure
            self.progress.emit(1, 9, "Initializing structure...")
            ExtractionInitializer.ensure_structure(self.screen.extraction_dir)
            ExtractionInitializer.repair_structure(self.screen.extraction_dir)

            # 2. Frames
            self.progress.emit(2, 9, "Extracting frames...")
            frame_extractor = FrameExtractor(fps=1)
            frames_dir = self.screen.extraction_dir / "frames"
            all_frames = frame_extractor.extract_frames(self.video_path, frames_dir)

            # 3. Gestures
            self.progress.emit(3, 9, "Detecting gestures...")
            gesture_detector = GestureDetector()
            gesture_positions = []
            gesture_regions = []
            for i, frame_path in enumerate(all_frames[:3]):
                frame = cv2.imread(str(frame_path))
                if frame is not None:
                    is_gesture, gx, gy = gesture_detector.detect_gesture_in_frame(frame)
                    if is_gesture and gx is not None and gy is not None:
                        gesture_positions.append({"x": gx, "y": gy})
                        gesture_regions.append({"x": gx, "y": gy, "frame_index": i})

            # 4. Brush Markings
            self.progress.emit(4, 9, "Analyzing manual markings...")
            marking_annotations = []
            overlay_path = self.screen.extraction_dir / "annotation_overlay.png"
            if overlay_path.exists():
                analyzer = AnnotationAnalyzer()
                ocr_p = OcrProcessor()
                markings = analyzer.analyze_overlay(self.screen.screenshot_path, overlay_path)
                for idx, m in enumerate(markings, start=1):
                    crop_path = analyzer.get_crop_path(self.screen.screenshot_path, m, self.screen.extraction_dir / "marked_regions", idx)
                    if crop_path:
                        marked_ocr = ocr_p.process(crop_path)
                        text = " ".join([r.get("text", "") for r in marked_ocr]).strip()
                        marking_annotations.append({
                            "index": 100 + idx,
                            "timestamp": 0.0,
                            "position": {
                                "x": (m["bbox"]["top_left"]["x"] + m["bbox"]["bottom_right"]["x"]) // 2,
                                "y": (m["bbox"]["top_left"]["y"] + m["bbox"]["bottom_right"]["y"]) // 2
                            },
                            "ocr_text": text or "N/A",
                            "spoken_text": "(Direct manual marking)",
                            "trigger_type": "text",
                            "region_image": f"marked_regions/marked_region_{idx:03d}.png"
                        })

            # 5. Full Screenshot OCR
            self.progress.emit(5, 9, "Running OCR analysis...")
            ocr_processor = OcrProcessor()
            full_screenshot_ocr = ocr_processor.process(self.screen.screenshot_path)

            # 6. Smart Select
            self.progress.emit(6, 9, "Selecting smart frames...")
            smart_selector = SmartSelector()
            selected_frames = smart_selector.select_frames(all_frames, self.settings)

            # 7. Triggers
            self.progress.emit(7, 9, "Detecting trigger words...")
            trigger_events = self.transcriber.detect_trigger_words(self.segments, self.settings.get("trigger_words", {}))

            # 8. Annotations
            self.progress.emit(8, 9, "Compiling annotations...")
            gesture_events = [{"timestamp": i * 1.0, "screenshot_position": pos} for i, pos in enumerate(gesture_positions)]
            annotations = ocr_processor.process_gesture_annotations(self.screen.extraction_dir.parent, gesture_events, self.segments)
            annotations.extend(marking_annotations)

            # 9. Export
            self.progress.emit(9, 9, "Exporting results...")
            extraction = ExtractionResult(
                screen=self.screen,
                video_path=self.video_path,
                audio_path=self.audio_path,
                all_frames=all_frames,
                selected_frames=selected_frames,
                gesture_positions=gesture_positions,
                gesture_regions=gesture_regions,
                ocr_results=full_screenshot_ocr,
                transcript_text=" ".join(str(seg.get("text", "")) for seg in self.segments).strip(),
                transcript_segments=self.segments,
                trigger_events=trigger_events,
                annotations=annotations,
            )
            
            # Read metadata
            import json
            metadata = {}
            if self.screen.metadata_path.exists():
                try: metadata = json.loads(self.screen.metadata_path.read_text(encoding="utf-8"))
                except: pass
            
            self.exporter.export(extraction, metadata=metadata, analysis_data={})
            self.finished.emit(self.screen)

        except Exception as e:
            logger.exception("PipelineWorker: Analysis failed")
            self.error.emit(str(e))
