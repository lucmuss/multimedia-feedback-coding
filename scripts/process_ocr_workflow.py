#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Complete OCR workflow integration example.

This script demonstrates how to integrate OCR processing into the ScreenReview pipeline.
It processes screenshots, extracts text, and shows how OCR data is used in AI analysis.
"""

from pathlib import Path
from screenreview.pipeline.ocr_processor import OcrProcessor


def main():
    """Run the complete OCR workflow example."""
    # Example project structure
    project_dir = Path("output/feedback")
    routes_dir = project_dir / "routes"

    if not routes_dir.exists():
        print(f"Routes directory not found: {routes_dir}")
        print("Please run the main application first to generate screenshots.")
        return

    print("=== ScreenReview OCR Workflow ===\n")

    # Step 1: Initialize OCR processor
    print("1. Initializing OCR processor...")
    processor = OcrProcessor(engine="auto", languages=["de", "en"])
    print("   ✓ OCR processor ready\n")

    # Step 2: Process all routes
    print("2. Processing OCR on all routes...")
    results = processor.process_route_screenshots(routes_dir)

    total_screenshots = 0
    total_texts = 0

    for route_slug, viewports in results.items():
        print(f"   Route: {route_slug}")
        for viewport, data in viewports.items():
            print(f"     {viewport}: {data['text_count']} texts found")
            total_screenshots += 1
            total_texts += data['text_count']
        print()

    print(f"   ✓ Processed {total_screenshots} screenshots, found {total_texts} text elements\n")

    # Step 3: Show OCR context for AI analysis
    print("3. OCR context for AI analysis:")
    for route_slug, viewports in results.items():
        for viewport, data in viewports.items():
            if data['text_count'] > 0:
                viewport_dir = Path(data['screenshot_path']).parent
                ocr_context = processor.get_ocr_context_for_prompt(viewport_dir)
                print(f"   {route_slug} ({viewport}):")
                print(f"     {ocr_context}")
                print()
                break  # Show only first example
        break  # Show only first route

    # Step 4: Demonstrate gesture OCR
    print("4. Gesture OCR example:")
    # Find a screenshot with OCR data
    example_screenshot = None
    for route_slug, viewports in results.items():
        for viewport, data in viewports.items():
            if data['text_count'] > 0:
                example_screenshot = Path(data['screenshot_path'])
                break
        if example_screenshot:
            break

    if example_screenshot and example_screenshot.exists():
        print(f"   Using screenshot: {example_screenshot}")

        # Simulate a gesture at the center of the screen
        from PIL import Image
        img = Image.open(example_screenshot)
        gesture_x, gesture_y = img.width // 2, img.height // 2
        print(f"   Simulating gesture at ({gesture_x}, {gesture_y})...")

        gesture_results = processor.process_gesture_region(
            example_screenshot, gesture_x, gesture_y, region_size=150
        )

        if gesture_results:
            print("   Found text in gesture region:")
            for entry in gesture_results[:3]:  # Show first 3 results
                print(f"     '{entry['text']}' (confidence: {entry['confidence']:.2f})")
        else:
            print("   No text found in gesture region")
    else:
        print("   No suitable screenshot found for gesture demo")

    print("\n=== Workflow Complete ===")
    print("\nOCR data is now available in .extraction/screenshot_ocr.json files")
    print("and will be automatically used in AI analysis prompts.")


if __name__ == "__main__":
    main()