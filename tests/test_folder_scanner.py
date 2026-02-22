# -*- coding: utf-8 -*-
"""Tests for project folder scanning."""

from __future__ import annotations

from pathlib import Path

import pytest

from screenreview.core.folder_scanner import scan_project


def test_scan_finds_all_pages_in_directory(tmp_project_dir: Path) -> None:
    screens = scan_project(tmp_project_dir, viewport_mode="mobile")
    assert len(screens) == 2


def test_scan_returns_screen_items(tmp_project_dir: Path) -> None:
    screens = scan_project(tmp_project_dir, viewport_mode="mobile")
    assert all(hasattr(screen, "route") for screen in screens)


def test_scan_filters_mobile_only_when_mobile_selected(tmp_project_dir: Path) -> None:
    screens = scan_project(tmp_project_dir, viewport_mode="mobile")
    assert all(screen.viewport == "mobile" for screen in screens)


def test_scan_filters_desktop_only_when_desktop_selected(tmp_project_dir: Path) -> None:
    screens = scan_project(tmp_project_dir, viewport_mode="desktop")
    assert all(screen.viewport == "desktop" for screen in screens)


def test_meta_json_loaded_for_each_screen(tmp_project_dir: Path) -> None:
    screens = scan_project(tmp_project_dir, viewport_mode="mobile")
    assert all(screen.metadata_path.name == "meta.json" for screen in screens)


def test_meta_contains_route_field(tmp_project_dir: Path) -> None:
    routes = [screen.route for screen in scan_project(tmp_project_dir, viewport_mode="mobile")]
    assert "/login.html" in routes


def test_meta_contains_viewport_field(tmp_project_dir: Path) -> None:
    screen = scan_project(tmp_project_dir, viewport_mode="mobile")[0]
    assert screen.viewport == "mobile"


def test_meta_contains_viewport_size(tmp_project_dir: Path) -> None:
    screen = scan_project(tmp_project_dir, viewport_mode="mobile")[0]
    assert screen.viewport_size == {"w": 390, "h": 844}


def test_meta_contains_git_branch_and_commit(tmp_project_dir: Path) -> None:
    screen = scan_project(tmp_project_dir, viewport_mode="mobile")[0]
    assert screen.git_branch == "main"
    assert screen.git_commit.startswith("8904800")


def test_meta_contains_browser(tmp_project_dir: Path) -> None:
    screen = scan_project(tmp_project_dir, viewport_mode="mobile")[0]
    assert screen.browser == "chromium"


def test_meta_contains_timestamp(tmp_project_dir: Path) -> None:
    screen = scan_project(tmp_project_dir, viewport_mode="mobile")[0]
    assert screen.timestamp_utc == "2026-02-21T21:43:57Z"


def test_transcript_md_path_set(tmp_project_dir: Path) -> None:
    screen = scan_project(tmp_project_dir, viewport_mode="mobile")[0]
    assert screen.transcript_path.name == "transcript.md"


def test_screenshot_path_set(tmp_project_dir: Path) -> None:
    screen = scan_project(tmp_project_dir, viewport_mode="mobile")[0]
    assert screen.screenshot_path.name == "screenshot.png"


def test_extraction_dir_created_if_missing(tmp_project_dir: Path) -> None:
    target = tmp_project_dir / "login_html" / "mobile" / ".extraction"
    if target.exists():
        target.rmdir()
    screens = scan_project(tmp_project_dir, viewport_mode="mobile")
    assert target.exists()
    assert any(screen.extraction_dir == target for screen in screens)


def test_missing_meta_json_skips_screen_with_warning(tmp_project_dir: Path, caplog) -> None:
    (tmp_project_dir / "login_html" / "mobile" / "meta.json").unlink()
    screens = scan_project(tmp_project_dir, viewport_mode="mobile")
    assert len(screens) == 1
    assert "meta.json is missing" in caplog.text


def test_missing_screenshot_skips_screen_with_warning(tmp_project_dir: Path, caplog) -> None:
    (tmp_project_dir / "login_html" / "mobile" / "screenshot.png").unlink()
    screens = scan_project(tmp_project_dir, viewport_mode="mobile")
    assert len(screens) == 1
    assert "screenshot.png is missing" in caplog.text


def test_missing_transcript_creates_template(tmp_project_dir: Path) -> None:
    transcript_path = tmp_project_dir / "login_html" / "mobile" / "transcript.md"
    transcript_path.unlink()
    screens = scan_project(tmp_project_dir, viewport_mode="mobile")
    assert transcript_path.exists()
    content = transcript_path.read_text(encoding="utf-8")
    assert "## Notes" in content
    assert any(screen.transcript_path == transcript_path for screen in screens)


def test_empty_directory_returns_empty_list(tmp_path: Path) -> None:
    assert scan_project(tmp_path, viewport_mode="mobile") == []


def test_screens_sorted_by_route(tmp_project_dir: Path) -> None:
    screens = scan_project(tmp_project_dir, viewport_mode="mobile")
    assert [screen.route for screen in screens] == sorted(screen.route for screen in screens)


def test_screen_item_has_all_fields(tmp_project_dir: Path) -> None:
    screen = scan_project(tmp_project_dir, viewport_mode="mobile")[0]
    assert screen.name
    assert screen.route
    assert screen.viewport
    assert isinstance(screen.viewport_size, dict)
    assert screen.screenshot_path.exists()
    assert screen.transcript_path.exists()
    assert screen.metadata_path.exists()
    assert screen.extraction_dir.exists()


def test_invalid_viewport_mode_raises_error(tmp_project_dir: Path) -> None:
    with pytest.raises(ValueError):
        scan_project(tmp_project_dir, viewport_mode="tablet")


def test_scan_supports_feedback_routes_wrapper(tmp_feedback_dir_with_routes: Path) -> None:
    screens = scan_project(tmp_feedback_dir_with_routes, viewport_mode="mobile")
    assert len(screens) == 2
    assert all(screen.viewport == "mobile" for screen in screens)
