# multimedia-feedback-coding

Phase 1 scaffold for a desktop review tool that scans a screenshot project directory,
shows metadata and screenshots, and supports basic navigation.

## Setup (Recommended: uv)

```bash
uv venv
uv sync --extra dev
```

## Run GUI

```bash
uv run python -m screenreview.main
# optional: start with project folder
uv run python -m screenreview.main /path/to/project
```

Alternative entrypoints:

```bash
uv run python -m screenreview.gui
uv run multimedia-feedback-coding-gui
```

## Quality / Tests

```bash
uv run pytest -q
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
```

## OCR Integration

The application includes local OCR processing using EasyOCR for extracting text from screenshots. This provides contextual information for AI analysis without requiring API calls.

### OCR Commands

```bash
# Process OCR on all routes in a project
just ocr-process-routes output/feedback/routes

# Process OCR on a single screenshot
just ocr-process-single output/feedback/routes/login/mobile/screenshot.png

# Extract OCR from a gesture region
just ocr-gesture output/feedback/routes/login/mobile/screenshot.png 195 420

# Show OCR context for AI analysis
just ocr-show output/feedback/routes/login/mobile

# Run complete OCR workflow demo
just ocr-workflow
```

### OCR in AI Analysis

OCR results are automatically integrated into AI analysis prompts:

```
## OCR Text Elements
OCR Text Elements: "Anmelden" at (120, 400), "Email" at (30, 200), "Passwort" at (30, 300)
```

### OCR Data Storage

OCR results are stored in `.extraction/screenshot_ocr.json` files within each viewport directory:

```json
[
  {
    "text": "Anmelden",
    "bbox": {
      "top_left": {"x": 120, "y": 400},
      "bottom_right": {"x": 270, "y": 440}
    },
    "confidence": 0.95
  }
]
```

## Gesture Detection + OCR

The application includes MediaPipe-based gesture detection that can track pointing gestures and combine them with OCR for precise UI feedback.

### Gesture Commands

```bash
# Process gesture annotations with OCR
just ocr-gestures screen_dir gestures.json --transcript-json transcript.json

# Run complete gesture + OCR workflow demo
just gesture-workflow
```

### Gesture Data Format

Gesture events are stored as JSON:

```json
[
  {
    "timestamp": 5.2,
    "frame_index": 156,
    "webcam_position": {"x": 320, "y": 240},
    "screenshot_position": {"x": 195, "y": 420}
  }
]
```

### Gesture Annotations

Gesture annotations combine OCR text with spoken feedback:

```json
[
  {
    "index": 1,
    "timestamp": 5.2,
    "position": {"x": 195, "y": 420},
    "ocr_text": "Anmelden",
    "spoken_text": "Der Anmelden-Button muss entfernt werden",
    "trigger_type": "remove",
    "region_image": "gesture_regions/region_195_420.png"
  }
]
```

### Transcript Integration

Gesture annotations are written to `transcript.md`:

```markdown
## Notes
- [00:05] 🔴 REMOVE: "Der Anmelden-Button muss entfernt werden"
  → Position: (195, 420) | OCR: "Anmelden" | Region: gesture_regions/region_195_420.png
```

## Complete Pipeline (AI Analysis Optional)

The application includes a complete pipeline that processes audio, video, gestures, OCR, and transcripts. **AI analysis is now optional** - you can choose to use expensive AI models or rely on local processing only.

### AI Analysis Toggle

In Settings → AI Analysis tab, you can enable/disable AI analysis:

- **✅ AI Analysis Enabled**: Uses Replicate/OpenRouter for advanced bug detection
- **❌ AI Analysis Disabled**: Local processing only (OCR, gestures, transcripts)

When AI is disabled, the system still creates comprehensive bug reports using:
- Trigger word detection from transcripts
- Gesture position analysis
- OCR text extraction
- Local pattern matching

### Pipeline Commands

```bash
# Run complete pipeline (audio + video + OCR + gestures + transcripts)
just complete-pipeline

# Individual components
just ocr-process-routes output/feedback/routes  # OCR processing
just gesture-workflow                          # Gesture + OCR workflow
```

### Pipeline Overview

```
DU VOR BEAMER
     │
     ├─→ Webcam ──→ Video ──→ Frames (FFmpeg, 0€)
     │                │         │
     │                │         └─→ Gestures (MediaPipe, 0€)
     │                │               │
     │                │               └─→ OCR Regions (EasyOCR, 0€)
     │                │
     │                └─→ Smart Select (Python, 0€)
     │
     └─→ Mikrofon ──→ Audio ──→ Transcribe (GPT-4o, ~0.006€)
                         │
                         └─→ Trigger Words (Python, 0€)

     meta.json ──→ Route, Viewport, Git
     ui-audit.json ──→ Layout Metrics

     ALLES ──→ transcript.md (complete bug report)
```

### Generated Files

After running the complete pipeline, each screen directory contains:

```
.extraction/
├── raw_video.mp4              # Webcam recording
├── raw_audio.wav              # Microphone recording
├── frames/                    # Extracted frames (1/sec)
│   ├── frame_0001.png
│   ├── frame_0002.png
│   └── ...
├── audio_transcription.json   # GPT-4o transcription
├── audio_segments.json        # Processed segments with triggers
├── gesture_events.json        # Detected pointing gestures
├── gesture_regions/           # OCR regions around gestures
│   ├── region_001.png
│   └── region_002.png
├── ocr_results/               # OCR data for regions
│   ├── screenshot_ocr.json    # Full screenshot OCR
│   ├── region_001_ocr.json
│   └── region_002_ocr.json
├── gesture_annotations.json   # Combined annotations
└── trigger_events.json        # Detected trigger words

transcript.md                  # Complete bug report
```

### transcript.md Output

```markdown
# Transcript (Voice -> Text)
Route: /login.html
Viewport: mobile
Size: 390x844
Branch: main
Commit: 8904800cd7d591afb43873fb76cb1fd5272ac957
Timestamp: 2026-02-21T21:43:57Z

## Audio-Transkription
Der Anmelden-Button muss entfernt werden. Das Passwort-Feld soll größer sein. Der Header passt so.

## Annotationen
- [00:05] 🔴 REMOVE: "Der Anmelden-Button muss entfernt werden"
  → Position: (195, 420) | OCR: "Anmelden"
  → Region: .extraction/gesture_regions/region_001.png

- [00:25] 🟡 RESIZE: "Das Passwort-Feld soll größer sein"
  → Position: (195, 350) | OCR: "Passwort eingeben"
  → Region: .extraction/gesture_regions/region_002.png

## Numbered refs
1: 🔴 REMOVE Anmelden – Der Anmelden-Button muss entfernt werden
2: 🟡 RESIZE Passwort eingeben – Das Passwort-Feld soll größer sein
```

### Cost Breakdown

| Component | Tool | Cost |
|-----------|------|------|
| Video Recording | OpenCV | 0.00€ |
| Audio Recording | PyAudio | 0.00€ |
| Frame Extraction | FFmpeg | 0.00€ |
| Gesture Detection | MediaPipe | 0.00€ |
| OCR Processing | EasyOCR | 0.00€ |
| Audio Transcription | GPT-4o | ~0.006€ |
| Trigger Detection | Python | 0.00€ |
| Report Generation | Python | 0.00€ |
| **Total per Screen** | | **~0.006€** |

**30 screens = ~0.18€ total** (only transcription costs money).

## Justfile Shortcuts

```bash
just setup
just run
just test
just check
just gui-screenshots
just ocr-process-routes output/feedback/routes
just ocr-workflow
just gesture-workflow
just complete-pipeline
```

## Python Fallback (without uv)

```bash
python3 -m pip install -e .[dev]
python3 -m screenreview.main
```
