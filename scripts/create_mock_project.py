# -*- coding: utf-8 -*-
"""Creates a dummy project for testing purposes."""

import json
import base64
from pathlib import Path

# 1x1 Transparent PNG
PNG_BYTES = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7+fJ8AAAAASUVORK5CYII=")

def create_mock_project(base_dir: Path):
    project_path = base_dir / "sample_mock_project"
    routes_path = project_path / "feedback" / "routes"
    routes_path.mkdir(parents=True, exist_ok=True)

    samples = [
        ("home", "/"),
        ("login", "/login"),
        ("settings", "/settings")
    ]

    for name, route in samples:
        for viewport in ["mobile", "desktop"]:
            vp_dir = routes_path / name / viewport
            vp_dir.mkdir(parents=True, exist_ok=True)
            
            # Write meta.json
            meta = {
                "route": route,
                "slug": name,
                "viewport": viewport,
                "timestamp_utc": "2026-02-26T18:00:00Z"
            }
            (vp_dir / "meta.json").write_text(json.dumps(meta, indent=2))
            
            # Write dummy screenshot
            (vp_dir / "screenshot.png").write_bytes(PNG_BYTES)
    
    print(f"Created mock project at: {project_path.absolute()}")
    return project_path

if __name__ == "__main__":
    create_mock_project(Path.cwd())
