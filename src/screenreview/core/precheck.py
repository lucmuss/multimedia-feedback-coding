# -*- coding: utf-8 -*-
"""Pre-recording environment validation."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Callable

from screenreview.core.folder_scanner import resolve_routes_root, scan_project


CheckResult = dict[str, Any]
FileReport = dict[str, Any]

REQUIRED_SCREEN_FILES = ("screenshot.png", "meta.json", "transcript.md")


def analyze_missing_screen_files(
    project_dir: Path,
    viewport_mode: str | None = None,
) -> FileReport:
    """Analyze route folders and report missing required files.

    If `viewport_mode` is None, both `mobile` and `desktop` are checked.
    """
    viewports = [viewport_mode] if viewport_mode in {"mobile", "desktop"} else ["mobile", "desktop"]
    missing: list[dict[str, str]] = []
    checked_folders = 0
    checked_slugs = 0

    routes_root = resolve_routes_root(project_dir)
    if not routes_root.exists() or not routes_root.is_dir():
        return {
            "project_dir": str(project_dir),
            "viewport_mode": viewport_mode,
            "checked_slugs": 0,
            "checked_folders": 0,
            "missing_count": 0,
            "missing": [],
            "exists": False,
        }

    slug_dirs = sorted([p for p in routes_root.iterdir() if p.is_dir()], key=lambda p: p.name)
    checked_slugs = len(slug_dirs)

    for slug_dir in slug_dirs:
        for viewport in viewports:
            vp_dir = slug_dir / viewport
            if not vp_dir.exists() or not vp_dir.is_dir():
                missing.append({"slug": slug_dir.name, "viewport": viewport, "missing": "folder"})
                continue
            checked_folders += 1
            for filename in REQUIRED_SCREEN_FILES:
                if not (vp_dir / filename).exists():
                    missing.append({"slug": slug_dir.name, "viewport": viewport, "missing": filename})

    return {
        "project_dir": str(project_dir),
        "viewport_mode": viewport_mode,
        "checked_slugs": checked_slugs,
        "checked_folders": checked_folders,
        "missing_count": len(missing),
        "missing": missing,
        "exists": True,
    }


def format_missing_file_report(report: FileReport, max_items: int = 20) -> str:
    """Create a readable text report for missing route files."""
    if not report.get("exists", True):
        return f"Project directory not found: {report.get('project_dir')}"

    missing = list(report.get("missing", []) or [])
    if not missing:
        return (
            "No missing route files detected.\n"
            f"Checked slugs: {report.get('checked_slugs', 0)}\n"
            f"Checked folders: {report.get('checked_folders', 0)}"
        )

    lines = [
        f"Missing route files detected: {len(missing)}",
        f"Checked slugs: {report.get('checked_slugs', 0)}",
        f"Checked folders: {report.get('checked_folders', 0)}",
        "",
    ]
    for row in missing[:max_items]:
        lines.append(f"- {row.get('slug')}/{row.get('viewport')}: {row.get('missing')}")
    if len(missing) > max_items:
        lines.append(f"- ... and {len(missing) - max_items} more")
    return "\n".join(lines)


class Precheck:
    """Run environment and project checks before a review session."""

    def __init__(
        self,
        *,
        webcam_check: Callable[[int], bool] | None = None,
        mic_check: Callable[[int], bool] | None = None,
        openai_validate: Callable[[str], bool] | None = None,
        replicate_validate: Callable[[str], bool] | None = None,
        openrouter_validate: Callable[[str], bool] | None = None,
        disk_usage_provider: Callable[[str], tuple[int, int, int]] | None = None,
        estimate_cost_fn: Callable[[int], float] | None = None,
    ) -> None:
        self.webcam_check = webcam_check or (lambda index: True)
        self.mic_check = mic_check or (lambda index: True)
        self.openai_validate = openai_validate or (lambda key: True if not key else key.startswith("sk-"))
        self.replicate_validate = replicate_validate or (lambda key: True if not key else key.startswith("r8_"))
        self.openrouter_validate = openrouter_validate or (
            lambda key: True if not key else key.startswith("sk-or-v1-")
        )
        self.disk_usage_provider = disk_usage_provider or shutil.disk_usage
        self.estimate_cost_fn = estimate_cost_fn or (lambda screens: round(screens * 0.03, 3))

    def run(self, project_dir: Path, settings: dict[str, Any]) -> list[CheckResult]:
        viewport_mode = str(settings.get("viewport", {}).get("mode", "mobile"))
        screens = scan_project(project_dir, viewport_mode=viewport_mode)
        candidate_dirs = self._candidate_viewport_dirs(project_dir, viewport_mode)

        webcam_index = int(settings.get("webcam", {}).get("camera_index", 0))
        mic_index = int(settings.get("webcam", {}).get("microphone_index", 0))
        openai_key = str(settings.get("api_keys", {}).get("openai", ""))
        replicate_key = str(settings.get("api_keys", {}).get("replicate", ""))
        openrouter_key = str(settings.get("api_keys", {}).get("openrouter", ""))

        results: list[CheckResult] = []
        
        # FFmpeg Check (Robust for Windows/Linux)
        ffmpeg_path = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
        ffmpeg_ok = False
        if ffmpeg_path:
            try:
                import subprocess
                subprocess.run([ffmpeg_path, "-version"], capture_output=True, check=True)
                ffmpeg_ok = True
            except Exception:
                ffmpeg_ok = False
        
        results.append(self._result("ffmpeg", ffmpeg_ok, "FFmpeg installed (required for video)"))
        
        results.append(self._result("webcam", self.webcam_check(webcam_index), "Webcam reachable"))
        results.append(self._result("microphone", self.mic_check(mic_index), "Microphone reachable"))

        has_screens = len(screens) > 0
        results.append(self._result("folder_structure", has_screens, f"Found {len(screens)} screen(s)"))
        results.append(
            self._result(
                "meta_json",
                bool(candidate_dirs) and all((p / "meta.json").exists() for p in candidate_dirs),
                "All viewport folders contain meta.json",
            )
        )
        results.append(
            self._result(
                "screenshot_png",
                bool(candidate_dirs) and all((p / "screenshot.png").exists() for p in candidate_dirs),
                "All viewport folders contain screenshot.png",
            )
        )

        results.append(self._result("openai_key", self.openai_validate(openai_key), "OpenAI API key valid"))
        results.append(
            self._result("replicate_key", self.replicate_validate(replicate_key), "Replicate API key valid")
        )
        results.append(
            self._result("openrouter_key", self.openrouter_validate(openrouter_key), "OpenRouter API key valid")
        )

        _total, _used, free = self.disk_usage_provider(str(project_dir))
        min_free = 1_000_000_000
        results.append(
            self._result(
                "disk_space",
                free >= min_free,
                f"Free space: {free} bytes (required >= {min_free})",
            )
        )

        estimated = float(self.estimate_cost_fn(len(screens)))
        results.append(
            {
                "check": "cost_estimation",
                "passed": True,
                "message": f"Estimated session cost: EUR {estimated:.3f}",
                "estimated_cost_euro": estimated,
                "screens": len(screens),
            }
        )
        return results

    def _result(self, check: str, passed: bool, message: str) -> CheckResult:
        return {"check": check, "passed": bool(passed), "message": message}

    def _candidate_viewport_dirs(self, project_dir: Path, viewport_mode: str) -> list[Path]:
        routes_root = resolve_routes_root(project_dir)
        if not routes_root.exists() or not routes_root.is_dir():
            return []
        candidates: list[Path] = []
        for page_dir in routes_root.iterdir():
            if not page_dir.is_dir():
                continue
            vp_dir = page_dir / viewport_mode
            if vp_dir.exists() and vp_dir.is_dir():
                candidates.append(vp_dir)
        return candidates
