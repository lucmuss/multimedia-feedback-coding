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

## Justfile Shortcuts

```bash
just setup
just run
just test
just check
just gui-screenshots
```

## Python Fallback (without uv)

```bash
python3 -m pip install -e .[dev]
python3 -m screenreview.main
```
