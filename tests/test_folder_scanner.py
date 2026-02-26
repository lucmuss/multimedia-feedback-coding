# -*- coding: utf-8 -*-
import pytest
from pathlib import Path
import json

from screenreview.core.folder_scanner import resolve_routes_root, scan_project
from screenreview.models.screen_item import ScreenItem
from screenreview.utils.file_utils import write_json_file, write_text_file


@pytest.fixture
def tmp_project_dir(tmp_path: Path) -> Path:
    """Create a temporary project structure for testing."""
    project = tmp_path / "test_project"
    slug = project / "login_html"
    mobile = slug / "mobile"
    mobile.mkdir(parents=True)
    
    write_json_file(mobile / "meta.json", {
        "route": "/login.html",
        "viewport": "mobile",
        "viewport_size": {"w": 390, "h": 844}
    })
    write_text_file(mobile / "screenshot.png", "fake_png")
    
    return project


def test_resolve_routes_root_direct(tmp_project_dir: Path) -> None:
    root = resolve_routes_root(tmp_project_dir)
    assert root == tmp_project_dir


def test_resolve_routes_root_nested(tmp_project_dir: Path) -> None:
    # Move slug to /routes/
    routes_dir = tmp_project_dir / "routes"
    routes_dir.mkdir()
    import shutil
    shutil.move(str(tmp_project_dir / "login_html"), str(routes_dir / "login_html"))
    
    root = resolve_routes_root(tmp_project_dir)
    assert root == routes_dir


def test_scan_project_finds_screens(tmp_project_dir: Path) -> None:
    screens = scan_project(tmp_project_dir, viewport_mode="mobile")
    assert len(screens) == 1
    item = screens[0]
    assert isinstance(item, ScreenItem)
    assert item.name == "login_html"
    assert item.route == "/login.html"
    assert item.viewport == "mobile"


def test_scan_project_sorts_by_route(tmp_project_dir: Path) -> None:
    # Add another slug
    slug2 = tmp_project_dir / "abc_html" # name is earlier but route is later
    mobile2 = slug2 / "mobile"
    mobile2.mkdir(parents=True)
    write_json_file(mobile2 / "meta.json", {"route": "/zzz.html"})
    write_text_file(mobile2 / "screenshot.png", "fake_png")
    
    screens = scan_project(tmp_project_dir)
    assert len(screens) == 2
    assert screens[0].route == "/login.html"
    assert screens[1].route == "/zzz.html"


def test_scan_project_prefers_mobile(tmp_project_dir: Path) -> None:
    # Add desktop to existing slug
    desktop = tmp_project_dir / "login_html" / "desktop"
    desktop.mkdir()
    write_json_file(desktop / "meta.json", {"viewport": "desktop"})
    write_text_file(desktop / "screenshot.png", "png")
    
    screens = scan_project(tmp_project_dir, viewport_mode="mobile")
    assert len(screens) == 1
    assert screens[0].viewport == "mobile"
    
    screens = scan_project(tmp_project_dir, viewport_mode="desktop")
    assert len(screens) == 1
    assert screens[0].viewport == "desktop"


def test_missing_meta_skips_screen(tmp_project_dir: Path) -> None:
    (tmp_project_dir / "login_html" / "mobile" / "meta.json").unlink()
    screens = scan_project(tmp_project_dir)
    assert len(screens) == 0


def test_missing_screenshot_skips_screen(tmp_project_dir: Path) -> None:
    (tmp_project_dir / "login_html" / "mobile" / "screenshot.png").unlink()
    screens = scan_project(tmp_project_dir)
    assert len(screens) == 0


def test_scan_project_no_template_creation(tmp_project_dir: Path) -> None:
    """Verify that scan_project no longer creates transcript files automatically."""
    transcript_path_md = tmp_project_dir / "login_html" / "mobile" / "transcript.md"
    
    if transcript_path_md.exists():
        transcript_path_md.unlink()
        
    screens = scan_project(tmp_project_dir, viewport_mode="mobile")
    assert len(screens) == 1
    assert not transcript_path_md.exists()


def test_scan_project_empty_dir(tmp_path: Path) -> None:
    assert scan_project(tmp_path) == []


def test_scan_project_invalid_viewport(tmp_project_dir: Path) -> None:
    with pytest.raises(ValueError, match="viewport_mode must be 'mobile' or 'desktop'"):
        scan_project(tmp_project_dir, viewport_mode="invalid")
