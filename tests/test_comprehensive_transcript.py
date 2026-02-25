# -*- coding: utf-8 -*-
import pytest
from pathlib import Path
from screenreview.pipeline.transcriber import Transcriber

def test_save_comprehensive_markdown(tmp_path):
    transcriber = Transcriber()
    output_path = tmp_path / "transcript.md"
    
    metadata = {
        "route": "/test",
        "viewport": "mobile",
        "viewport_size": {"w": 390, "h": 844},
        "git": {"branch": "main", "commit": "abc"},
        "timestamp_utc": "2026-02-25"
    }
    
    transcript = {
        "text": "Der Button muss weg.",
        "segments": [{"start": 1.0, "end": 3.0, "text": "Der Button muss weg."}]
    }
    
    trigger_events = [{"time": 1.0, "type": "remove", "word": "weg"}]
    
    annotations = [{
        "index": 1,
        "timestamp": 1.5,
        "position": {"x": 100, "y": 200},
        "ocr_text": "Anmelden",
        "spoken_text": "Der Button muss weg.",
        "trigger_type": "remove",
        "region_image": "region_001.png"
    }]
    
    ocr_results = [{
        "text": "Anmelden",
        "bbox": {"top_left": {"x": 80, "y": 180}, "bottom_right": {"x": 120, "y": 220}},
        "confidence": 0.95
    }]
    
    transcriber.save_to_markdown(
        transcript=transcript,
        metadata=metadata,
        trigger_events=trigger_events,
        output_path=output_path,
        annotations=annotations,
        ocr_results=ocr_results,
        analysis_summary="KI-Analyse: Button entfernen."
    )
    
    content = output_path.read_text(encoding="utf-8")
    
    assert "# ScreenReview Transcript & Analysis" in content
    assert "**Route:** `/test`" in content
    assert "🔴 REMOVE: \"Der Button muss weg.\"" in content
    assert "## 🤲 Gesten & Kontext (Annotationen)" in content
    assert "### Annotation 1 (🔴 REMOVE)" in content
    assert "**OCR am Zeigepunkt:** \"Anmelden\"" in content
    assert "## 🔍 Vollständiger Screenshot OCR" in content
    assert "| Anmelden | (100, 200) | 0.95 |" in content
    assert "## 🤖 KI-Zusammenfassung & Empfehlungen" in content
    assert "KI-Analyse: Button entfernen." in content
    assert "1: 🔴 REMOVE **Anmelden** – Der Button muss weg." in content
