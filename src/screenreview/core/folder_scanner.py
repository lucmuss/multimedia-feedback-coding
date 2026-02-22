# -*- coding: utf-8 -*-
"""Scan project folders and build ScreenItem objects."""

from __future__ import annotations

import logging
from pathlib import Path

from screenreview.constants import DEFAULT_TRANSCRIPT_TEMPLATE
from screenreview.models.screen_item import ScreenItem
from screenreview.utils.file_utils import ensure_dir, read_json_file, write_text_file

logger = logging.getLogger(__name__)


def _build_transcript_template(route: str, viewport: str) -> str:
    return DEFAULT_TRANSCRIPT_TEMPLATE.format(route=route or "-", viewport=viewport or "-")


def _is_slug_dir(path: Path) -> bool:
    if not path.is_dir():
        return False
    return (path / "mobile").is_dir() or (path / "desktop").is_dir()


def resolve_routes_root(project_dir: str | Path) -> Path:
    """Return the effective routes root.

    Supports both:
    - <project>/<slug>/<viewport>/...
    - <project>/routes/<slug>/<viewport>/...
    """
    root = Path(project_dir)
    if not root.exists() or not root.is_dir():
        return root

    routes_dir = root / "routes"
    if not routes_dir.exists() or not routes_dir.is_dir():
        return root

    direct_slug_dirs = [p for p in root.iterdir() if p.is_dir() and p.name != "routes" and _is_slug_dir(p)]
    nested_slug_dirs = [p for p in routes_dir.iterdir() if p.is_dir() and _is_slug_dir(p)]
    if nested_slug_dirs and not direct_slug_dirs:
        return routes_dir
    return root


def _read_screen_item(base_dir: Path, viewport_dir: Path) -> ScreenItem | None:
    meta_path = viewport_dir / "meta.json"
    screenshot_path = viewport_dir / "screenshot.png"
    transcript_path = viewport_dir / "transcript.md"
    extraction_dir = ensure_dir(viewport_dir / ".extraction")

    if not meta_path.exists():
        logger.warning("Skipping screen because meta.json is missing: %s", viewport_dir)
        return None
    if not screenshot_path.exists():
        logger.warning("Skipping screen because screenshot.png is missing: %s", viewport_dir)
        return None

    metadata = read_json_file(meta_path)
    route = str(metadata.get("route", ""))
    viewport = str(metadata.get("viewport", viewport_dir.name))
    viewport_size = metadata.get("viewport_size", {}) or {}
    timestamp_utc = str(metadata.get("timestamp_utc", ""))
    git_branch = str(metadata.get("git", {}).get("branch", ""))
    git_commit = str(metadata.get("git", {}).get("commit", ""))
    browser = str(metadata.get("playwright", {}).get("browser", ""))

    if not transcript_path.exists():
        write_text_file(transcript_path, _build_transcript_template(route=route, viewport=viewport))

    return ScreenItem(
        name=base_dir.name,
        route=route,
        viewport=viewport,
        viewport_size=viewport_size,
        timestamp_utc=timestamp_utc,
        git_branch=git_branch,
        git_commit=git_commit,
        browser=browser,
        screenshot_path=screenshot_path,
        transcript_path=transcript_path,
        metadata_path=meta_path,
        extraction_dir=extraction_dir,
    )


def scan_project(project_dir: str | Path, viewport_mode: str = "mobile") -> list[ScreenItem]:
    """Scan a project directory and return screen items sorted by route."""
    root = resolve_routes_root(project_dir)
    if not root.exists() or not root.is_dir():
        return []
    if viewport_mode not in {"mobile", "desktop"}:
        raise ValueError("viewport_mode must be 'mobile' or 'desktop'")

    screens: list[ScreenItem] = []
    for page_dir in sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.name.lower()):
        viewport_dir = page_dir / viewport_mode
        if not viewport_dir.exists() or not viewport_dir.is_dir():
            continue
        item = _read_screen_item(page_dir, viewport_dir)
        if item is not None:
            screens.append(item)

    screens.sort(key=lambda item: item.route or item.name)
    return screens
