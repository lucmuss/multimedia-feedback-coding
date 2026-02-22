# -*- coding: utf-8 -*-
"""Tests for precheck validation."""

from __future__ import annotations

from pathlib import Path

from screenreview.core.precheck import Precheck, analyze_missing_screen_files, format_missing_file_report


def _result_map(results: list[dict]) -> dict[str, dict]:
    return {item["check"]: item for item in results}


def test_all_checks_pass_with_valid_setup(tmp_project_dir: Path, default_config: dict) -> None:
    default_config["api_keys"]["openai"] = "sk-test"
    default_config["api_keys"]["replicate"] = "r8_test"
    precheck = Precheck(
        webcam_check=lambda idx: True,
        mic_check=lambda idx: True,
        openai_validate=lambda key: True,
        replicate_validate=lambda key: True,
        disk_usage_provider=lambda path: (10, 1, 2_000_000_000),
        estimate_cost_fn=lambda screens: 0.12,
    )
    results = _result_map(precheck.run(tmp_project_dir, default_config))
    assert all(item["passed"] for key, item in results.items() if key != "cost_estimation")


def test_webcam_check_fails_without_camera(tmp_project_dir: Path, default_config: dict) -> None:
    precheck = Precheck(webcam_check=lambda idx: False)
    results = _result_map(precheck.run(tmp_project_dir, default_config))
    assert results["webcam"]["passed"] is False


def test_microphone_check_fails_without_mic(tmp_project_dir: Path, default_config: dict) -> None:
    precheck = Precheck(mic_check=lambda idx: False)
    results = _result_map(precheck.run(tmp_project_dir, default_config))
    assert results["microphone"]["passed"] is False


def test_folder_check_fails_with_empty_dir(tmp_path: Path, default_config: dict) -> None:
    precheck = Precheck()
    results = _result_map(precheck.run(tmp_path, default_config))
    assert results["folder_structure"]["passed"] is False


def test_meta_json_check_fails_when_missing(tmp_project_dir: Path, default_config: dict) -> None:
    (tmp_project_dir / "login_html" / "mobile" / "meta.json").unlink()
    precheck = Precheck()
    results = _result_map(precheck.run(tmp_project_dir, default_config))
    assert results["meta_json"]["passed"] is False


def test_screenshot_check_fails_when_missing(tmp_project_dir: Path, default_config: dict) -> None:
    (tmp_project_dir / "login_html" / "mobile" / "screenshot.png").unlink()
    precheck = Precheck()
    results = _result_map(precheck.run(tmp_project_dir, default_config))
    assert results["screenshot_png"]["passed"] is False


def test_openai_key_check_fails_with_invalid_key(tmp_project_dir: Path, default_config: dict) -> None:
    default_config["api_keys"]["openai"] = "bad"
    precheck = Precheck(openai_validate=lambda key: False)
    results = _result_map(precheck.run(tmp_project_dir, default_config))
    assert results["openai_key"]["passed"] is False


def test_replicate_key_check_fails_with_invalid_key(tmp_project_dir: Path, default_config: dict) -> None:
    default_config["api_keys"]["replicate"] = "bad"
    precheck = Precheck(replicate_validate=lambda key: False)
    results = _result_map(precheck.run(tmp_project_dir, default_config))
    assert results["replicate_key"]["passed"] is False


def test_openrouter_key_check_fails_with_invalid_key(tmp_project_dir: Path, default_config: dict) -> None:
    default_config["api_keys"]["openrouter"] = "bad"
    precheck = Precheck(openrouter_validate=lambda key: False)
    results = _result_map(precheck.run(tmp_project_dir, default_config))
    assert results["openrouter_key"]["passed"] is False


def test_disk_space_check_fails_when_low(tmp_project_dir: Path, default_config: dict) -> None:
    precheck = Precheck(disk_usage_provider=lambda path: (10, 9, 123))
    results = _result_map(precheck.run(tmp_project_dir, default_config))
    assert results["disk_space"]["passed"] is False


def test_cost_estimation_calculated(tmp_project_dir: Path, default_config: dict) -> None:
    precheck = Precheck(estimate_cost_fn=lambda screens: 0.42)
    results = _result_map(precheck.run(tmp_project_dir, default_config))
    assert results["cost_estimation"]["estimated_cost_euro"] == 0.42


def test_returns_detailed_check_results(tmp_project_dir: Path, default_config: dict) -> None:
    precheck = Precheck()
    results = precheck.run(tmp_project_dir, default_config)
    assert all({"check", "passed", "message"}.issubset(item.keys()) for item in results)


def test_analyze_missing_screen_files_reports_no_missing(tmp_project_dir: Path) -> None:
    report = analyze_missing_screen_files(tmp_project_dir, viewport_mode="mobile")
    assert report["exists"] is True
    assert report["missing_count"] == 0
    assert report["checked_folders"] == 2


def test_analyze_missing_screen_files_reports_missing_transcript(tmp_project_dir: Path) -> None:
    (tmp_project_dir / "login_html" / "mobile" / "transcript.md").unlink()
    report = analyze_missing_screen_files(tmp_project_dir, viewport_mode="mobile")
    assert report["missing_count"] == 1
    assert report["missing"][0]["missing"] == "transcript.md"


def test_analyze_missing_screen_files_reports_missing_folder(tmp_project_dir: Path) -> None:
    desktop_dir = tmp_project_dir / "dashboard_html" / "desktop"
    for child in desktop_dir.iterdir():
        child.unlink()
    desktop_dir.rmdir()
    report = analyze_missing_screen_files(tmp_project_dir, viewport_mode=None)
    assert any(row["missing"] == "folder" and row["viewport"] == "desktop" for row in report["missing"])


def test_analyze_missing_screen_files_handles_nonexistent_project(tmp_path: Path) -> None:
    report = analyze_missing_screen_files(tmp_path / "missing", viewport_mode="mobile")
    assert report["exists"] is False
    assert report["missing_count"] == 0


def test_format_missing_file_report_lists_items() -> None:
    report = {
        "exists": True,
        "checked_slugs": 2,
        "checked_folders": 2,
        "missing_count": 2,
        "missing": [
            {"slug": "login_html", "viewport": "mobile", "missing": "meta.json"},
            {"slug": "login_html", "viewport": "mobile", "missing": "screenshot.png"},
        ],
    }
    text = format_missing_file_report(report)
    assert "Missing route files detected: 2" in text
    assert "login_html/mobile: meta.json" in text


def test_format_missing_file_report_no_missing_message() -> None:
    text = format_missing_file_report(
        {
            "exists": True,
            "checked_slugs": 1,
            "checked_folders": 2,
            "missing_count": 0,
            "missing": [],
        }
    )
    assert "No missing route files detected" in text
