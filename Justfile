set shell := ["bash", "-c"]

default:
    @just --list

setup:
    uv venv
    uv sync --extra dev

run:
    uv run python -m screenreview.main

run-project project_dir:
    uv run python -m screenreview.main {{project_dir}}

test:
    uv run pytest -q

lint:
    uv run ruff check src tests
    uv run ruff format --check src tests

format:
    uv run ruff format src tests
    uv run ruff check --fix src tests

typecheck:
    uv run mypy src

check: lint typecheck test

gui-screenshots:
    uv run python scripts/capture_phase1_gui_screenshots.py

ocr-process-routes routes_dir:
    uv run python -m screenreview.cli.ocr_cli process-routes {{routes_dir}} --verbose

ocr-process-single screenshot_path:
    uv run python -m screenreview.cli.ocr_cli process-single {{screenshot_path}}

ocr-gesture screenshot_path x y:
    uv run python -m screenreview.cli.ocr_cli gesture-ocr {{screenshot_path}} {{x}} {{y}}

ocr-show viewport_dir:
    uv run python -m screenreview.cli.ocr_cli show-ocr {{viewport_dir}}

ocr-gestures screen_dir gestures_json:
    uv run python -m screenreview.cli.ocr_cli process-gestures {{screen_dir}} {{gestures_json}}

ocr-workflow:
    uv run python scripts/process_ocr_workflow.py

gesture-workflow:
    uv run python scripts/process_gesture_workflow.py

complete-pipeline:
    uv run python scripts/process_complete_pipeline.py
