# -*- coding: utf-8 -*-
"""System diagnostics utility for AI agents and developers."""

import sys
import os
import shutil
import json
import logging
from pathlib import Path
from typing import Any

# Add src to path if running directly
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from screenreview.config import load_config
from screenreview.core.precheck import Precheck
from screenreview.integrations.openai_client import OpenAIClient
from screenreview.integrations.replicate_client import ReplicateClient
from screenreview.integrations.openrouter_client import OpenRouterClient

def run_diagnostics() -> dict[str, Any]:
    """Runs a full suite of system diagnostic checks."""
    settings = load_config()
    report = {
        "status": "ok",
        "system": {
            "os": os.name,
            "platform": sys.platform,
            "python_version": sys.version,
            "cwd": os.getcwd(),
        },
        "dependencies": {},
        "config": {},
        "api_keys": {},
        "errors": []
    }

    # 1. Check Dependencies
    ffmpeg_path = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    report["dependencies"]["ffmpeg"] = {
        "found": bool(ffmpeg_path),
        "path": ffmpeg_path
    }
    if not ffmpeg_path:
        report["status"] = "error"
        report["errors"].append("FFmpeg not found in PATH. Video recording will fail.")

    # 2. Check Disk Space
    try:
        total, used, free = shutil.disk_usage(".")
        report["system"]["disk"] = {
            "free_gb": round(free / (2**30), 2),
            "total_gb": round(total / (2**30), 2)
        }
    except Exception as e:
        report["errors"].append(f"Disk check failed: {e}")

    # 3. Check API Keys (Validation)
    api_keys = settings.get("api_keys", {})
    clients = {
        "openai": OpenAIClient(api_key=api_keys.get("openai", "")),
        "replicate": ReplicateClient(api_key=api_keys.get("replicate", "")),
        "openrouter": OpenRouterClient(api_key=api_keys.get("openrouter", ""))
    }

    for name, client in clients.items():
        key = api_keys.get(name, "")
        if not key:
            report["api_keys"][name] = "missing"
        else:
            try:
                # Format check only to be fast
                is_valid_format = client.validate_key(key, check_remote=False)
                report["api_keys"][name] = "format_ok" if is_valid_format else "invalid_format"
            except Exception:
                report["api_keys"][name] = "error"

    # 4. Check Folders
    logs_dir = Path("logs")
    report["system"]["logs_dir"] = {
        "exists": logs_dir.exists(),
        "writable": os.access(logs_dir, os.W_OK) if logs_dir.exists() else False
    }

    return report

def main():
    print("Running Multimedia Feedback Coding Diagnostics...")
    report = run_diagnostics()
    
    # Save report for AI agents
    report_path = Path("logs/diagnostic_report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    
    # Print summary
    print(f"\nDiagnostic Report saved to: {report_path.absolute()}")
    print("-" * 40)
    print(f"Status: {report['status'].upper()}")
    print(f"OS: {report['system']['os']}")
    print(f"FFmpeg: {'FOUND' if report['dependencies']['ffmpeg']['found'] else 'NOT FOUND'}")
    
    for err in report["errors"]:
        print(f"ERROR: {err}")
    
    if report["status"] == "error":
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
