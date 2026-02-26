# Projektstatus (Project Status)

Dieses Dokument gibt einen Überblick über den aktuellen Stand der Entwicklung, implementierte Features und geplante Aufgaben.

## Aktueller Stand: Phase 3 (GUI & Integration)

### ✅ Abgeschlossene Meilensteine

#### Phase 1, 2 & 3: Production Ready
- **Daten-Scanner:** Automatisches Einlesen von Projektstrukturen (Routes/Screenshots).
- **Rekorder:** Stabilisierte Aufnahme von Webcam (OpenCV) und Audio (SoundDevice).
- **Manual Annotations:** Interaktiver Brush zum Markieren von UI-Bugs direkt am Screenshot.
- **Smart-Selector:** Gestenerkennung (MediaPipe) und OCR-Prozessoren fertiggestellt.
- **Multimodale KI:** Integration von GPT-4o und Vision-Modellen via OpenRouter/Replicate.
- **UX Refinement:** 
    - Auto-Retract Dropdowns (Scale, Viewport, Brush).
    - Recent Projects Navigation (Schnellzugriff).
    - Preflight-Check Robustheit (FFmpeg Mocking Support).
- **Testing:** 200+ Test-Cases für GUI, Pipeline und Integrations-Flows.

### 📋 Geplante Aufgaben (Roadmap)
- [ ] **Erweiterte Konfiguration:** Export-Templates für verschiedene Zielformate (Jira, PDF).
- [ ] **Live-Streaming:** Direkte Anzeige des Webcam-Feeds in der Hauptansicht (über der Annotation).
- [ ] **History-Browser:** Ansicht früherer Analyseergebnisse innerhalb der App.

## Architektur-Metadaten für KI-Agenten
- **Sprache:** Python 3.10+
- **Framework:** PyQt6 (UI), OpenCV (Video), SoundDevice (Audio)
- **Entry Point:** `src/screenreview/main.py`
- **Config:** `settings.json` (wird automatisch generiert)
- **Detaillierte AI-Docs:** `AI_AGENTS.md`
