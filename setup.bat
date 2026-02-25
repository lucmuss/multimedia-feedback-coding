@echo off
REM Windows Setup Script für multimedia-feedback-coding
REM Dieses Script installiert alle erforderlichen Dependencies

echo.
echo ====================================================
echo  multimedia-feedback-coding - Windows Setup
echo ====================================================
echo.

REM Überprüfe ob uv installiert ist
where uv >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ❌ ERROR: uv ist nicht installiert!
    echo.
    echo Installation von uv:
    echo   - Downloade von: https://github.com/astral-sh/uv
    echo   - Oder: pip install uv
    echo.
    pause
    exit /b 1
)

echo ✓ uv gefunden

REM Erstelle virtuelle Umgebung
echo.
echo Creating virtual environment...
call uv venv
if %ERRORLEVEL% NEQ 0 (
    echo ❌ ERROR: Konnte venv nicht erstellen
    pause
    exit /b 1
)

echo ✓ Virtual environment erstellt

REM Installiere Dependencies
echo.
echo Installing dependencies...
echo   - Tesseract OCR (Default engine)
echo   - MediaPipe (Gesture detection)
echo   - And other core components...
call uv sync --extra dev
if %ERRORLEVEL% NEQ 0 (
    echo ❌ ERROR: Konnte Dependencies nicht installieren
    pause
    exit /b 1
)

echo ✓ Core dependencies installiert

REM Optionale OCR-Extended Dependencies
echo.
echo.
echo ====================================================
echo  Optional: Zusätzliche OCR-Engines installieren?
echo ====================================================
echo.
echo Das Projekt beinhaltet Tesseract OCR standardmäßig.
echo.
echo Optional können Sie zusätzliche OCR-Engines installieren:
echo  - EasyOCR (schnell, genau)
echo  - PaddleOCR (Alternative)
echo.

setlocal enabledelayedexpansion
set /p install_extended="Möchten Sie die zusätzlichen OCR-Engines installieren? (j/n) "

if /i "!install_extended!"=="j" (
    echo.
    echo Installing optional OCR engines...
    call uv sync --extra ocr-extended
    if !ERRORLEVEL! NEQ 0 (
        echo ❌ WARNING: Konnte ocr-extended nicht installieren
        echo Sie können dies später mit folgendem Befehl versuchen:
        echo   uv sync --extra ocr-extended
    ) else (
        echo ✓ Optional OCR engines installiert
    )
)

echo.
echo ====================================================
echo  ✓ Setup abgeschlossen!
echo ====================================================
echo.
echo Verfügbare Befehle:
echo.
echo   GUI starten:
echo     uv run python -m screenreview.main
echo     or just run
echo.
echo   Tests ausführen:
echo     uv run pytest -q
echo     or just test
echo.
echo   Qualitätsprüfen:
echo     uv run ruff check src tests
echo     or just lint
echo.
echo OCR-Engines im Settings konfigurierbar:
echo   Settings (GUI) → Gesture & OCR → OCR Engine
echo.
echo Weitere Informationen: README.md
echo.
pause
