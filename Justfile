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
