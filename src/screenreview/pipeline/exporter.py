# -*- coding: utf-8 -*-
"""Write extracted artifacts and transcript output back to the project folders."""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any

from screenreview.models.extraction_result import ExtractionResult
from screenreview.pipeline.transcriber import Transcriber
from screenreview.utils.file_utils import ensure_dir, write_json_file

logger = logging.getLogger(__name__)


class Exporter:
    """Export transcript and extraction artifacts."""

    def __init__(self, transcriber: Transcriber | None = None) -> None:
        self.transcriber = transcriber or Transcriber()

    def export(
        self,
        extraction: ExtractionResult,
        metadata: dict[str, Any],
        analysis_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Write transcript, analysis, OCR results, and gesture region images."""
        logger.info(f"[B9] Starting export for screen: {extraction.screen.name}")
        logger.debug(f"[B9] Extraction dir: {extraction.screen.extraction_dir}")
        logger.debug(f"[B9] Transcript path: {extraction.screen.transcript_path}")

        extraction_dir = ensure_dir(extraction.screen.extraction_dir)
        logger.debug(f"[B9] Extraction directory ensured: {extraction_dir}")

        transcript_result = {
            "text": extraction.transcript_text,
            "segments": extraction.transcript_segments,
        }
        logger.debug(f"[B9] Transcript data: {len(extraction.transcript_segments)} segments, {len(extraction.transcript_text)} chars")

        # Gather data for comprehensive transcript
        analysis_summary = (analysis_data or {}).get("summary")
        
        transcript_path = self.transcriber.save_to_markdown(
            transcript=transcript_result,
            metadata=metadata,
            trigger_events=extraction.trigger_events,
            output_path=extraction.screen.transcript_path,
            annotations=extraction.annotations,
            ocr_results=extraction.ocr_results,
            analysis_summary=analysis_summary,
        )
        logger.info(f"[B9] Transcript saved to: {transcript_path}")

        analysis_path = extraction_dir / "analysis.json"
        self._write_analysis_json(analysis_path, analysis_data or {})

        ocr_paths = self._write_ocr_results(extraction_dir, extraction.ocr_results)
        gesture_paths = self._write_gesture_regions(extraction_dir, extraction.gesture_regions)

        return {
            "transcript": transcript_path,
            "analysis": analysis_path,
            "ocr_dir": extraction_dir,
            "gesture_dir": extraction_dir / "gesture_regions",
            "ocr_count": len(ocr_paths),
            "gesture_count": len(gesture_paths),
        }

    def _write_analysis_json(self, path: Path, analysis_data: dict[str, Any]) -> None:
        existing: dict[str, Any] = {}
        if path.exists():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    existing = loaded
            except Exception:
                existing = {}
        merged = dict(existing)
        merged.update(analysis_data)
        write_json_file(path, merged)

    def _write_ocr_results(self, extraction_dir: Path, ocr_results: list[dict[str, Any]]) -> list[Path]:
        written: list[Path] = []
        for result in ocr_results:
            frame_name = str(result.get("frame", "frame_0001.png"))
            if frame_name.endswith(".png"):
                file_name = frame_name[:-4] + "_ocr.json"
            else:
                file_name = frame_name + "_ocr.json"
            target = extraction_dir / file_name
            payload = dict(result)
            write_json_file(target, payload)
            written.append(target)
        return written

    def _write_gesture_regions(self, extraction_dir: Path, gesture_regions: list[Path]) -> list[Path]:
        target_dir = ensure_dir(extraction_dir / "gesture_regions")
        written: list[Path] = []
        for index, source_path in enumerate(gesture_regions, start=1):
            target = target_dir / f"region_{index:03d}.png"
            if source_path.exists():
                if source_path.resolve() != target.resolve():
                    shutil.copyfile(source_path, target)
                else:
                    target.write_bytes(source_path.read_bytes())
            written.append(target)
        return written
