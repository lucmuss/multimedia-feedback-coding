# ScreenReview Datenfluss - Detaillierte Analyse

## Übersicht

Dieses Dokument beschreibt den vollständigen Datenfluss durch das ScreenReview-System, von der initialen Aufnahme bis zum finalen Bug-Report. Das System ist modular aufgebaut und kann sowohl mit als auch ohne KI-Analyse betrieben werden.

## Architektur-Übersicht

```
┌─────────────────────────────────────────────────────────┐
│                        GUI Layer                         │
│  Settings │ Viewer │ Controls │ Preview │ Progress │ Cost │
└─────┬──────────┬──────────┬──────────────────────────────┘
      │          │          │
      │     User Events     │
      │  (Record/Next/Skip) │
      │          │          │
      ▼          ▼          ▼
┌─────────────────────────────────────────────────────────┐
│                    Queue Manager                         │
│         (ThreadPoolExecutor, max 2 Workers)              │
│                                                         │
│  Screen 1: [B1→B2→B3→B4→B5→B6→B7→B8→B9]              │
│  Screen 2: [B1→B2→B3→...] (parallel)                   │
│                                                         │
│  Signals → GUI:                                         │
│    progress_updated(screen, step, total, message)        │
│    task_completed(screen, result)                        │
│    cost_updated(total, entry)                           │
└─────┬──────────────────────────────────────┬────────────┘
      │                                      │
      ▼                                      ▼
┌──────────────────┐              ┌──────────────────────┐
│  Pipeline Layer  │              │    Storage Layer      │
│                  │              │                       │
│  B1: FFmpeg      │──────────→  │  .extraction/frames/  │
│  B2: Smart Select│──────────→  │  .extraction/         │
│  B3: MediaPipe   │──────────→  │    gesture_events.json│
│  B4: EasyOCR     │──────────→  │    ocr_results/       │
│  B5: GPT-4o STT  │──────────→  │    audio_*.json       │
│  B6: Triggers    │──────────→  │    trigger_events.json│
│  B7: Korrelation │──────────→  │    annotations.json   │
│  B8: Analyse*    │──────────→  │    analysis.json      │
│  B9: Export      │──────────→  │  transcript.md [2]    │
└──────────────────┘              └──────────────────────┘

* B8 ist optional (Ollama/Cloud oder lokal)
```

## Detaillierter Datenfluss

### Phase 1: Initialisierung & Setup

#### 1.1 Projekt-Setup
```
Input:  Projekt-Verzeichnis (z.B. output/feedback/)
Output: Validierte Projektstruktur

Steps:
├── Prüfe routes/ Verzeichnis
├── Scanne alle Slugs (login_html/, swipe_overview_html/, ...)
├── Pro Slug prüfe:
│   ├── mobile/ vorhanden?
│   ├── desktop/ vorhanden?
│   ├── screenshot.png vorhanden?
│   ├── meta.json vorhanden und valide? [1]
│   │   → Enthält route, viewport, viewport_size, git, playwright
│   └── transcript.md vorhanden? [2]
│       → Falls nicht: erstelle Template mit Header aus meta.json [1]
├── Erstelle .extraction/ pro Screen falls nötig
├── Lade vorhandene QA-Daten (falls verfügbar):
│   ├── ui-audit.json → Layout-Metriken, Consistency-Findings [5]
│   ├── link-check-report.json → Broken Links [5]
│   ├── e2e-report.json → E2E-Status [5]
│   └── Falls vorhanden: Vorausfüllung der transcript.md [2]
│       mit Auto-Detected Issues aus QA-Daten [5]
└── Setze Standard-Settings
```

#### 1.2 Settings-Validierung
```
Input:  settings.json + API Keys
Output: Validierte Konfiguration

Components:
├── API Key Validation (OpenAI, Replicate, OpenRouter)
├── Device Detection (Camera, Microphone)
├── Model Availability Check
└── Settings Persistence
```

### Phase 2: Live-Aufnahme (Recording)

#### 2.1 Screen laden
```
Input:  Aktueller Screen aus Navigator
Output: Screenshot + Metadaten in GUI

Steps:
├── Navigator gibt aktuellen Screen zurück
├── Lade screenshot.png und zeige im Viewer
├── Lade meta.json [1] und zeige Metadaten:
│   Route: /login.html [1]
│   Viewport: mobile [1]
│   Size: 390x844 [1]
│   Branch: main [1]
│   Commit: 8904800... [1]
│   Browser: chromium [1]
├── Falls QA-Daten vorhanden [5]:
│   Zeige Pre-Analysis Score (green/yellow/red)
│   Zeige Auto-Detected Issues
└── Status: "Bereit für Aufnahme"
```

#### 2.2 Hardware-Initialisierung
```
Input:  Device Indices aus Settings
Output: Initialisierte Capture-Streams

Components:
├── Camera Stream (OpenCV)
├── Audio Stream (PyAudio)
├── Level Monitoring (Background Thread)
└── Preview Generation (QImage)
```

#### 2.3 Aufnahme starten (Ctrl+R)
```
Input:  Ctrl+R (Start)
Output: Laufende Aufnahme-Threads

Steps:
├── Speicherpfade festlegen:
│   Video: {slug}/{viewport}/.extraction/raw_video.mp4
│   Audio: {slug}/{viewport}/.extraction/raw_audio.wav
├── Video-Thread starten:
│   OpenCV VideoCapture(camera_index)
│   VideoWriter(raw_video.mp4, MP4V, 25fps, 1080p)
├── Audio-Thread starten:
│   PyAudio Stream(rate=16000, channels=1, format=INT16)
│   Schreibe WAV-Header
├── GUI Updates starten:
│   Webcam-Preview (alle 120ms)
│   Audio-Level-Meter (alle 120ms)
│   Aufnahme-Timer (jede 1000ms)
└── Status: "● REC 00:00"
```

#### 2.4 Aufnahme stoppen (Ctrl+N oder Ctrl+S)
```
Input:  Ctrl+N (Next) oder Ctrl+S (Stop)
Output: raw_video.mp4 + raw_audio.wav gespeichert

Steps:
├── Video-Thread stoppen → raw_video.mp4 finalisiert
├── Audio-Thread stoppen → raw_audio.wav finalisiert
├── GUI Updates stoppen
├── Dateigröße prüfen (> 0 Bytes)
├── Task in Queue legen → Phase 3 startet im Hintergrund
├── Falls Ctrl+N: Sofort nächsten Screen laden (2.1)
└── Falls Ctrl+S: Auf aktuellem Screen bleiben
```

### Phase 3: Post-Processing Pipeline
(Läuft im Hintergrund, GUI nie blockiert)

Reihenfolge und Abhängigkeiten:

B1: Frames extrahieren
    Eingabe:  .extraction/raw_video.mp4
    Tool:     FFmpeg (lokal, 0€)
    Ausgabe:  .frames/frame_0001.png ... frame_XXXX.png
    Abhängig von: Nichts (erster Schritt)
    Fortschritt: "Frames extrahieren: X von Y"
         │
         ▼
B2: Smart Selector
    Eingabe:  .frames/frame_*.png + .extraction/raw_audio.wav
    Tools:    MediaPipe + OpenCV + Audio-Level (alle lokal, 0€)
    Ausgabe:  .frames/selected/frame_*.png
    Abhängig von: B1
    Logik:
    ├── Lade alle Frames aus .frames/
    ├── Für jeden Frame berechne 3 Scores:
    │   ├── Gesten-Score: MediaPipe → Hand sichtbar + Zeigefinger?
    │   ├── Audio-Score: Audio-Level zum Frame-Zeitpunkt > 0.1?
    │   └── Diff-Score: Pixel-Differenz zum vorherigen Frame > 5%?
    ├── Frame behalten wenn mindestens 1 Score positiv
    ├── Immer behalten: erster + letzter Frame
    ├── Maximum: max_frames_per_screen aus Settings
    └── Kopiere ausgewählte Frames nach .frames/selected/
    Fortschritt: "Smart Select: X von Y Frames ausgewählt"
         │
         ▼
B3: Gesten-Erkennung (detailliert)
    Eingabe:  .frames/selected/frame_*.png
    Tool:     MediaPipe Hands (lokal, 0€)
    Ausgabe:  .extraction/gesture_events.json
    Abhängig von: B2
    Logik:
    ├── Für jeden selected Frame:
    │   ├── Frame laden (OpenCV BGR → RGB)
    │   ├── MediaPipe Hands.process(frame)
    │   ├── Falls Hand erkannt:
    │   │   ├── Prüfe Zeigegeste:
    │   │   │   Zeigefinger ausgestreckt (landmark[8].y < landmark[6].y)
    │   │   │   Andere Finger eingeklappt
    │   │   ├── Fingerspitze = landmark[8]
    │   │   ├── Webcam-Koordinaten (pixel)
    │   │   ├── Umrechnung auf Screenshot-Koordinaten:
    │   │   │   Nutze viewport_size aus meta.json [1]
    │   │   │   (390x844 für mobile [1])
    │   │   └── Speichere Event mit Timestamp
    │   └── Falls keine Hand: Frame überspringen
    └── Speichere als gesture_events.json
    Fortschritt: "Gesten: X erkannt in Y Frames"
         │
         ▼
B4: Brush Markings & Intelligent OCR
    Eingabe:  screenshot.png + annotation_overlay.png + gesture_events.json
    Tools:    AnnotationAnalyzer + OcrProcessor (Pillow + EasyOCR)
    Ausgabe:  .extraction/marked_regions/marked_region_*.png
              .extraction/ocr_results/screenshot_ocr.json
    Abhängig von: B3
    Logik:
    ├── A) Manuelle Markierungen (Brush):
    │   ├── AnnotationAnalyzer erkennt Pixel-Cluster im Overlay
    │   ├── Automatischer Zuschnitt (Crops) der markierten Stellen
    │   └── OCR auf diesen Ausschnitten liefert direkten Kontext
    ├── B) Gesten-Regionen:
    │   ├── 200x200px Bereich um MediaPipe-Koordinaten ausschneiden
    │   └── OCR zur Identifikation des fokussierten UI-Elements
    └── C) Screenshot-OCR (komplett)
    Logik:
    ├── A) Screenshot-OCR (komplett):
    │   ├── EasyOCR auf screenshot.png
    │   ├── Alle erkannten Texte mit Position + Konfidenz
    │   └── Speichere als screenshot_ocr.json
    ├── B) Für jede Gesten-Position:
    │   ├── 200x200px Bereich aus screenshot.png ausschneiden
    │   ├── Region speichern als region_XXX.png
    │   ├── EasyOCR auf Region anwenden
    │   ├── Koordinaten umrechnen (Region → Screenshot)
    │   └── Speichere als region_XXX_ocr.json
    └── Ergebnis: "Anmelden" bei (195, 420) etc.
    Fortschritt: "OCR: X Texte erkannt"
         │
         ▼
B5: Audio transkribieren                    ← EINZIGER CLOUD-SCHRITT
    Eingabe:  .extraction/raw_audio.wav
    Tool:     OpenAI GPT-4o Transcribe (Cloud, ~0,6 Cent/Min)
    Ausgabe:  .extraction/audio_transcription.json
              .extraction/audio_transcription.txt
              .extraction/audio_segments.json
    Abhängig von: Nichts (kann parallel zu B1-B4 laufen!)
    Logik:
    ├── Audio an OpenAI API senden
    ├── Sprache: Deutsch (aus Settings)
    ├── Format: verbose_json mit Segment-Timestamps
    ├── Ergebnis parsen:
    │   ├── audio_transcription.json (komplett mit Metadaten)
    │   ├── audio_transcription.txt (nur Volltext)
    │   └── audio_segments.json (nur Segmente mit Timestamps)
    └── Kosten tracken → Cost Widget aktualisieren
    Fortschritt: "Transkription: abgeschlossen (0,006€)"
         │
         ▼
B6: Trigger-Wörter erkennen
    Eingabe:  .extraction/audio_segments.json
    Tool:     Python String-Matching (lokal, 0€)
    Ausgabe:  .extraction/trigger_events.json
    Abhängig von: B5
    Logik:
    ├── Für jedes Segment:
    │   ├── Text in Kleinbuchstaben
    │   ├── Suche nach Trigger-Wörtern (aus Settings):
    │   │   ├── "bug","fehler","falsch"      → bug 🔴
    │   │   ├── "ok","passt","gut"           → ok ✅
    │   │   ├── "entfernen","weg","löschen"  → remove 🔴
    │   │   ├── "größer","kleiner"           → resize 🟡
    │   │   ├── "verschieben","bewegen"      → move 🟡
    │   │   ├── "farbe","style"              → restyle 🟡
    │   │   └── "wichtig","dringend"         → high_priority 🔴
    │   ├── Mehrere Trigger pro Segment möglich
    │   └── Primärer Trigger = erster gefundener (nach Priorität)
    └── Speichere als trigger_events.json
    Fortschritt: "Trigger: X erkannt"
         │
         ▼
B7: Korrelation (Alles zusammenführen)
    Eingabe:  gesture_events.json
              + audio_segments.json
              + trigger_events.json
              + ocr_results/region_*_ocr.json
    Tool:     Python (lokal, 0€)
    Ausgabe:  .extraction/annotations.json
    Abhängig von: B3 + B4 + B5 + B6 (alle müssen fertig sein)
    Logik:
    ├── Für jede Geste:
    │   ├── Finde Audio-Segment wo:
    │   │   segment.start <= geste.timestamp <= segment.end
    │   │   (Toleranz: ±2 Sekunden)
    │   ├── Finde Trigger für dieses Segment
    │   ├── Finde OCR-Text für diese Position
    │   └── Erstelle Annotation:
    │       {
    │         index, timestamp,
    │         position: {x, y},
    │         ocr_text: "Anmelden",
    │         spoken_text: "Der Button muss weg",
    │         trigger_type: "remove",
    │         region_image: "gesture_regions/region_001.png"
    │       }
    ├── Falls Segmente OHNE Geste:
    │   └── Trotzdem als Annotation aufnehmen
    │       (Position: null, nur Text + Trigger)
    └── Sortiere nach Timestamp
    Fortschritt: "Korrelation: X Annotationen erstellt"
         │
         ▼
B8: KI-Analyse (OPTIONAL)
    Eingabe:  annotations.json + screenshot.png + selected frames
    Tool:     Ollama lokal (0€) ODER Cloud (Replicate/OpenRouter)
    Ausgabe:  .extraction/analysis.json
    Abhängig von: B7
    ├── Falls deaktiviert: Überspringe → weiter zu B9
    ├── Falls Ollama:
    │   ├── Prompt bauen mit meta.json [1] Daten
    │   ├── Bilder als Base64 kodieren
    │   ├── POST http://localhost:11434/api/generate
    │   └── Kosten: 0,00€
    └── Falls Cloud:
        ├── Prompt + Bilder an API senden
        └── Kosten tracken
    Fortschritt: "Analyse: abgeschlossen"
         │
         ▼
B9: transcript.md schreiben
    Eingabe:  annotations.json + meta.json [1] + audio_transcription.txt
              + screenshot_ocr.json + analysis.json (optional)
    Tool:     Python (lokal, 0€)
    Ausgabe:  transcript.md [2] (befüllt)
    Abhängig von: B7 (oder B8 falls KI aktiv)
    Logik:
    ├── Header aus meta.json [1]:
    │   Route, Viewport, Size, Browser, Branch, Commit, Timestamp
    ├── Audio-Transkription (Volltext)
    ├── Annotationen mit Icons:
    │   🔴 für bug/remove/high_priority
    │   🟡 für resize/move/restyle
    │   ✅ für ok
    │   📝 für unklassifiziert
    ├── Screenshot OCR (alle Texte)
    ├── Falls KI-Analyse vorhanden:
    │   └── KI-generierte Bug-Zusammenfassung
    ├── Numbered Refs (priorisierte Liste)
    └── Schreibe transcript.md [2]
    Fortschritt: "Export: transcript.md geschrieben ✅"

Parallelisierung innerhalb eines Screens:

Thread 1 (Video-Pipeline):     Thread 2 (Audio-Pipeline):
B1: Frames extrahieren          B5: Audio transkribieren
         │                               │
         ▼                               ▼
B2: Smart Selector              B6: Trigger-Wörter
         │                               │
         ▼                               │
B3: Gesten-Erkennung                     │
         │                               │
         ▼                               │
B4: OCR                                  │
         │                               │
         └───────────┬───────────────────┘
                     │
                     ▼
              B7: Korrelation
                     │
                     ▼
              B8: KI-Analyse (optional)
                     │
                     ▼
              B9: Export transcript.md [2]

Zeitersparnis: ~30-40% weil Audio und Video
parallel verarbeitet werden.

### Phase 4: Annotations & Korrelation

#### 4.1 Zeitbasierte Korrelation
```
Input:  gesture_events.json + audio_segments.json
Output: gesture_annotations.json

Algorithm:
├── For each gesture event:
│   ├── Find closest audio segment by timestamp
│   ├── Match within ±2 second tolerance
│   ├── Extract OCR text from gesture region
│   ├── Apply trigger classification
│   └── Create annotation record
└── Sort by timestamp
```

#### 4.2 Lokale Analyse (Fallback)
```
Input:  transcript_segments + gesture_positions
Output: Local bug reports

Algorithm:
├── Simple keyword matching (bug, fehler, remove, etc.)
├── Gesture position analysis
├── Priority assignment (high/medium/low)
└── Basic issue categorization
```

### Phase 5: KI-Analyse (Optional)

#### 5.1 Prompt-Generierung
```
Input:  extraction_result + settings
Output: Formatted prompt for AI model

Components:
├── Screenshot + Gesture Regions
├── OCR Context Integration
├── Transcript Segments
├── Meta Data (route, viewport, git)
└── Instruction Template
```

#### 5.2 AI-Model-Aufruf
```
Input:  Images + Prompt + API Key
Output: Raw AI response

Providers:
├── Replicate (llama_32_vision, qwen_vl)
├── OpenRouter (gpt4o_vision, llama_32_vision, qwen_vl)
└── Fallback: Local analysis
```

#### 5.3 Response-Parsing
```
Input:  Raw AI response (JSON/markdown)
Output: Structured bug reports

Algorithm:
├── JSON Detection & Parsing
├── Markdown Table Parsing
├── Issue Normalization (id, element, position, etc.)
├── Priority Mapping
└── Validation & Defaults
```

### Phase 6: Report-Generierung

#### 6.1 transcript.md Assembly
```
Input:  annotations.json + meta.json + transcript.json
Output: transcript.md (final bug report)

Structure:
├── Header (Route, Viewport, Size, Git, Timestamp)
├── Audio-Transkription (full text)
├── Annotationen (zeitgesteuert mit OCR)
├── Numbered Refs (priorisierte Liste)
└── Footer (OCR summary, metadata)
```

#### 6.2 Export-Formate
```
Input:  analysis_result
Output: markdown/json exports

Formats:
├── Markdown (human readable)
├── JSON (machine readable)
└── Auto-export after analysis (configurable)
```

## Zentrale Ordnerstruktur

```
{slug}/
└── {viewport}/                          (mobile oder desktop)
    ├── screenshot.png                   (von capture [3])
    ├── meta.json                        [1]
    ├── transcript.md                    [2]
    │
    ├── .frames/                         (von ScreenReview AI)
    │   ├── frame_0001.png              ← B1
    │   ├── frame_0002.png
    │   ├── ...
    │   └── selected/                   ← B2
    │       ├── frame_0003.png
    │       └── ...
    │
    └── .extraction/                     (von ScreenReview AI)
        ├── raw_video.mp4               ← Phase 2 (Aufnahme)
        ├── raw_audio.wav               ← Phase 2 (Aufnahme)
        │
        ├── frames/                     ← B1 (Frame-Extraktion)
        │   ├── frame_0001.png
        │   ├── frame_0002.png
        │   └── ...
        │
        ├── audio_transcription.json    ← B5 (komplett)
        ├── audio_transcription.txt     ← B5 (nur Text)
        ├── audio_segments.json         ← B5 (mit Timestamps)
        │
        ├── trigger_events.json         ← B6
        ├── gesture_events.json         ← B3
        │
        ├── gesture_regions/            ← B4
        │   ├── region_001.png
        │   └── ...
        │
        ├── ocr_results/               ← B4
        │   ├── screenshot_ocr.json
        │   ├── region_001_ocr.json
        │   └── ...
        │
        ├── annotations.json           ← B7 (alles zusammen)
        ├── analysis.json              ← B8 (optional, KI)
        └── debug.log                  ← Logging
```

## Datenformate & Schnittstellen

### Core Data Structures

#### ExtractionResult
```python
@dataclass
class ExtractionResult:
    screen: ScreenInfo
    selected_frames: List[Path]
    gesture_positions: List[Dict[str, Any]]
    transcript_segments: List[Dict[str, Any]]
    ocr_results: Dict[str, Any]
```

#### AnalysisResult
```python
@dataclass
class AnalysisResult:
    screen: ScreenInfo
    bugs: List[Dict[str, Any]]
    summary: str
    raw_response: str
    model_used: str
    cost_euro: float
```

### JSON Schema Examples

#### gesture_events.json
```json
[
  {
    "timestamp": 10.5,
    "frame_index": 3,
    "webcam_position": {"x": 320, "y": 240},
    "screenshot_position": {"x": 195, "y": 420}
  }
]
```

#### audio_segments.json
```json
[
  {
    "start": 8.0,
    "end": 12.0,
    "text": "Der Button muss entfernt werden",
    "triggers": [
      {"type": "remove", "word": "entfernt", "text": "..."}
    ],
    "primary_trigger": "remove"
  }
]
```

#### gesture_annotations.json
```json
[
  {
    "index": 1,
    "timestamp": 10.5,
    "position": {"x": 195, "y": 420},
    "ocr_text": "Anmelden",
    "spoken_text": "Der Button muss entfernt werden",
    "trigger_type": "remove",
    "region_image": "gesture_regions/region_001.png"
  }
]
```

## Fehlerbehandlung & Fallbacks

### Component-Level Fallbacks

#### MediaPipe nicht verfügbar
```
→ GestureDetector.__init__() graceful degradation
→ Logging warning, continue without gesture detection
→ Smart Selector relies only on audio levels
```

#### FFmpeg nicht verfügbar
```
→ FrameExtractor.extract_frames() returns empty list
→ Logging error, skip frame-based analysis
→ Continue with screenshot-only OCR
```

#### EasyOCR nicht verfügbar
```
→ OcrProcessor uses fallback text extraction
→ Empty OCR results, continue with gesture-only
→ transcript.md notes missing OCR
```

#### API Keys fehlen
```
→ Analyzer._create_local_analysis_result()
→ Local trigger-based analysis
→ Cost = 0.0, model_used = "local"
```

#### B5 GPT-4o Transcribe fehlschlägt
```
├── Fallback 1: Whisper lokal (falls installiert)
│   pip install openai-whisper
│   whisper raw_audio.wav --model small --language de
├── Fallback 2: Whisper auf Replicate
│   (falls Replicate Key vorhanden)
├── Fallback 3: Ohne Transkription fortfahren
│   → audio_transcription.txt = "(Transkription fehlgeschlagen)"
│   → annotations.json nur mit Gesten + OCR (kein gesprochener Text)
│   → transcript.md [2] enthält Hinweis:
│     "⚠️ Audio-Transkription fehlgeschlagen – nur OCR-Daten"
```

#### Beamer-Region nicht kalibriert
```
├── Fallback: Verwende gesamten Frame als Beamer-Bereich
├── Gesten-Koordinaten sind ungenauer aber nutzbar
└── Hinweis in transcript.md [2]:
    "⚠️ Beamer-Region nicht kalibriert – Positionen approximiert"
```

#### Keine Gesten erkannt (z.B. Stock nicht sichtbar)
```
├── Alle Frames werden trotzdem behalten
├── OCR läuft auf gesamtem Screenshot
├── Transkript wird ohne Positionsangaben geschrieben
└── transcript.md [2] enthält nur Audio-Text ohne Position
```

### Pipeline-Level Resilience

#### Einzelne Componenten fehlschlagen
```
→ Continue with remaining components
→ Partial results in transcript.md
→ Clear indication of missing data
```

#### Vollständiger Pipeline-Abbruch
```
→ Save intermediate results
→ Generate partial transcript.md
→ User notification with recovery options
```

## Performance & Ressourcen

### Memory Usage
```
Base Application: ~50MB
With MediaPipe: +200MB
With EasyOCR: +500MB
With Large Images: +100MB per screenshot
Peak: ~1GB during full pipeline
```

### CPU/GPU Usage
```
Frame Extraction: CPU intensive (FFmpeg)
Gesture Detection: CPU/GPU (MediaPipe)
OCR Processing: CPU/GPU (EasyOCR)
AI Analysis: GPU preferred (Replicate/OpenRouter)
Audio Processing: CPU (Whisper local)
```

### Network Usage
```
Audio Transcription: ~0.006€ per minute
AI Analysis: 0.01-0.02€ per screenshot
Total per 30min session: ~0.18-0.60€
```

## Monitoring & Debugging

### Log Levels
```
DEBUG: Detailed component operations
INFO: Major pipeline steps completion
WARNING: Missing dependencies, API failures
ERROR: Component failures, data corruption
```

### Debug Output
```
.extraction/debug.log
├── Timestamped operations
├── Performance metrics
├── API call details (sanitized)
└── Error stack traces
```

### Health Checks
```
API Connectivity: Settings dialog validation
Device Availability: Test Webcam/Audio buttons
Model Access: Test Models button
Pipeline Integrity: Preflight check
```

## Erweiterbarkeit

### Neue AI Provider
```
1. Implement Client class (integrations/new_provider_client.py)
2. Add to Analyzer.__init__()
3. Update SettingsDialog._build_analysis_tab()
4. Add MODEL_PRICE_EURO entry
5. Test with _compute_api_validation_result()
```

### Neue Trigger-Kategorien
```
1. Add to TriggerDetector.TRIGGER_WORDS
2. Update PRIORITY_ORDER if needed
3. Add icon mapping in transcript generation
4. Test with sample transcripts
```

### Neue Export-Formate
```
1. Implement exporter (pipeline/new_exporter.py)
2. Add to SettingsDialog._build_export_tab()
3. Update Exporter class
4. Add file extension handling
```

## Testing & Debugging der Pipeline (Anweisungen für AI-Agenten)

Für die kontinuierliche Entwicklung und Fehlersuche stehen spezifische Skripte und Methoden bereit:

### 1. Komponenten-Check (`test_pipeline_check.py`)
Dieses Skript validiert, ob alle Basis-Komponenten und deren Abhängigkeiten erfolgreich importiert werden können. Es sollte nach jeder Änderung an den Dependencies oder Core-Klassen (z. B. `GestureDetector`, `OCRProcessor`) ausgeführt werden:
```bash
uv run python3 test_pipeline_check.py
```

### 2. Pipeline-Dry-Run auf Realdaten (`scripts/debug_pipeline.py`)
Dieses Skript ist ideal, um die einzelnen Pipeline-Schritte (Frame Extraction, Gestenerkennung, OCR) isoliert und ohne Cloud-Kosten auf **echten Aufnahme-Daten** zu testen.

*   **Voraussetzung:** Es muss ein gültiger Extraktionsordner vorhanden sein (mit `raw_video.avi` und `raw_audio.wav`).
*   **Wichtiger Tipp für PaddleOCR:** Um lange Wartezeiten durch Modell-Quellen-Checks (insbesondere ohne Netzwerkverbindung oder in CI/CD) zu vermeiden, nutze das Flag:
    ```bash
    export PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
    uv run python3 scripts/debug_pipeline.py
    ```
*   **OCR-Qualität:** Beachte, dass die OCR auf den verkleinerten Video-Frames oft schlechtere Ergebnisse liefert als auf dem finalen High-Res `screenshot.png` der Route. Um OCR explizit auf Qualität zu testen, wende die `OCRProcessor.process()`-Methode direkt auf den `screenshot.png` an.

### 3. Spezifische Backend-Anpassungen (Hardware/Treiber)
*   **GoPro/UDP-Streams:** Wenn VideoCapture für Netzwerk-Streams verwendet wird, ist das `cv2.CAP_FFMPEG`-Backend zwingend zu bevorzugen. Parameter wie `?overrun_nonfatal=1&fifo_size=50000000` verhindern Latenzen.
*   **Windows Camera Exceptions:** Hardware-Kameras können bei `cv2.VideoCapture.set()`-Aufrufen (z. B. für Framerate oder Auflösung) hart crashen (`Unknown C++ exception`). Diese Aufrufe müssen in der Pipeline immer in defensive `try...except`-Blöcke gewrappt sein.
*   **MediaPipe Legacy vs. Tasks:** Die Pipeline verwendet in Version `0.10.x` die alte `solutions`-API. Auf einigen System-Plattformen ist dieser Namespace defekt. Der `GestureDetector` ist so gebaut, dass er diesen Ausfall "graceful" behandelt und einfach keine Gesten liefert, anstatt die gesamte Pipeline zum Stillstand zu bringen.

Dieses Dokument beschreibt den vollständigen Datenfluss durch ScreenReview. Das System ist robust designed mit umfassenden Fallback-Mechanismen und kann sowohl vollständig lokal als auch mit Cloud-Komponenten betrieben werden.
