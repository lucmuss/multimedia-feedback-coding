# -*- coding: utf-8 -*-
"""CLI commands for OCR processing."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import typer

from screenreview.pipeline.ocr_processor import OcrProcessor

app = typer.Typer(help="OCR processing commands for screenshots")
logger = logging.getLogger(__name__)


@app.command()
def process_routes(
    routes_dir: Path = typer.Argument(..., help="Path to routes directory"),
    engine: str = typer.Option("auto", help="OCR engine: auto, easyocr"),
    languages: list[str] = typer.Option(["de", "en"], help="OCR languages"),
    verbose: bool = typer.Option(False, help="Verbose output")
) -> None:
    """Process OCR on all screenshots in routes directory."""
    if verbose:
        logging.basicConfig(level=logging.INFO)

    processor = OcrProcessor(engine=engine, languages=languages)

    typer.echo(f"Processing OCR on routes in: {routes_dir}")
    typer.echo(f"Using engine: {engine}, languages: {languages}")

    results = processor.process_route_screenshots(routes_dir)

    total_screenshots = 0
    total_texts = 0

    for route_slug, viewports in results.items():
        typer.echo(f"\nRoute: {route_slug}")
        for viewport, data in viewports.items():
            typer.echo(f"  {viewport}: {data['text_count']} texts found")
            total_screenshots += 1
            total_texts += data['text_count']

    typer.echo(f"\nTotal: {total_screenshots} screenshots processed, {total_texts} text elements found")


@app.command()
def process_single(
    screenshot_path: Path = typer.Argument(..., help="Path to screenshot"),
    output_path: Path = typer.Option(None, help="Output JSON path (default: screenshot_ocr.json)"),
    engine: str = typer.Option("auto", help="OCR engine: auto, easyocr"),
    languages: list[str] = typer.Option(["de", "en"], help="OCR languages")
) -> None:
    """Process OCR on a single screenshot."""
    processor = OcrProcessor(engine=engine, languages=languages)

    typer.echo(f"Processing OCR on: {screenshot_path}")

    ocr_results = processor.ocr_engine.extract_text(screenshot_path)

    ocr_data = []
    for entry in ocr_results:
        ocr_data.append({
            "text": entry["text"],
            "bbox": {
                "top_left": {"x": entry["bbox"][0], "y": entry["bbox"][1]},
                "bottom_right": {"x": entry["bbox"][2], "y": entry["bbox"][3]}
            },
            "confidence": round(entry["confidence"], 3)
        })

    if output_path is None:
        output_path = screenshot_path.with_suffix(".ocr.json")

    output_path.write_text(
        __import__("json").dumps(ocr_data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    typer.echo(f"Found {len(ocr_data)} text elements")
    typer.echo(f"Results saved to: {output_path}")


@app.command()
def gesture_ocr(
    screenshot_path: Path = typer.Argument(..., help="Path to screenshot"),
    x: int = typer.Argument(..., help="Gesture X coordinate"),
    y: int = typer.Argument(..., help="Gesture Y coordinate"),
    region_size: int = typer.Option(100, help="Region size around gesture"),
    engine: str = typer.Option("auto", help="OCR engine: auto, easyocr"),
    languages: list[str] = typer.Option(["de", "en"], help="OCR languages")
) -> None:
    """Extract OCR from a gesture region."""
    processor = OcrProcessor(engine=engine, languages=languages)

    typer.echo(f"Processing gesture OCR at ({x}, {y}) on: {screenshot_path}")

    results = processor.process_gesture_region(screenshot_path, x, y, region_size)

    if results:
        typer.echo("Found text in gesture region:")
        for entry in results:
            typer.echo(f"  '{entry['text']}' (confidence: {entry['confidence']:.2f})")
    else:
        typer.echo("No text found in gesture region")


@app.command()
def show_ocr(
    viewport_dir: Path = typer.Argument(..., help="Path to viewport directory")
) -> None:
    """Display OCR results for a viewport directory."""
    processor = OcrProcessor()

    ocr_context = processor.get_ocr_context_for_prompt(viewport_dir)

    typer.echo("OCR Context for AI Analysis:")
    typer.echo(ocr_context)


@app.command()
def process_gestures(
    screen_dir: Path = typer.Argument(..., help="Path to screen directory (mobile/desktop)"),
    gestures_json: Path = typer.Argument(..., help="Path to gestures JSON file"),
    transcript_json: Path = typer.Option(None, help="Path to transcript JSON file"),
    engine: str = typer.Option("auto", help="OCR engine: auto, easyocr"),
    languages: list[str] = typer.Option(["de", "en"], help="OCR languages")
) -> None:
    """Process gesture annotations with OCR and transcript matching."""
    processor = OcrProcessor(engine=engine, languages=languages)

    # Load gesture events
    try:
        gesture_events = json.loads(gestures_json.read_text(encoding="utf-8"))
    except Exception as e:
        typer.echo(f"Failed to load gestures: {e}", err=True)
        raise typer.Exit(1)

    # Load transcript segments
    transcript_segments = []
    if transcript_json and transcript_json.exists():
        try:
            transcript_segments = json.loads(transcript_json.read_text(encoding="utf-8"))
        except Exception as e:
            typer.echo(f"Failed to load transcript: {e}", err=True)
            raise typer.Exit(1)

    typer.echo(f"Processing {len(gesture_events)} gesture events...")

    annotations = processor.process_gesture_annotations(
        screen_dir, gesture_events, transcript_segments
    )

    typer.echo(f"Created {len(annotations)} annotations")

    # Show summary
    trigger_counts = {}
    for ann in annotations:
        trigger = ann.get("trigger_type") or "unknown"
        trigger_counts[trigger] = trigger_counts.get(trigger, 0) + 1

    typer.echo("\nTrigger summary:")
    for trigger, count in trigger_counts.items():
        typer.echo(f"  {trigger}: {count}")


if __name__ == "__main__":
    app()