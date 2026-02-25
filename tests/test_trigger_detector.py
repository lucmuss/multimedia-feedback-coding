# -*- coding: utf-8 -*-
import pytest
from screenreview.pipeline.trigger_detector import TriggerDetector

def test_trigger_detection_bug():
    detector = TriggerDetector()
    text = "Ich habe hier einen Fehler im Button gefunden."
    triggers = detector.detect_triggers(text)
    assert any(t["type"] == "bug" for t in triggers)

def test_trigger_detection_ok():
    detector = TriggerDetector()
    text = "Das sieht alles gut aus."
    triggers = detector.detect_triggers(text)
    assert any(t["type"] == "ok" for t in triggers)

def test_trigger_priority():
    detector = TriggerDetector()
    # "Fehler" (bug) has higher priority than "ok" (ok)
    text = "Das ist ein Fehler, aber sonst ok."
    primary = detector.classify_feedback(text)
    assert primary == "bug"

def test_process_segments():
    detector = TriggerDetector()
    segments = [
        {"start": 0.0, "end": 2.0, "text": "Hallo zusammen."},
        {"start": 2.0, "end": 5.0, "text": "Hier ist ein Bug."},
    ]
    processed = detector.process_transcript_segments(segments)
    assert processed[0]["primary_trigger"] is None
    assert processed[1]["primary_trigger"] == "bug"
    assert len(processed[1]["triggers"]) > 0

def test_empty_text():
    detector = TriggerDetector()
    assert detector.detect_triggers("") == []
    assert detector.classify_feedback("   ") is None
