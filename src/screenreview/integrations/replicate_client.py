# -*- coding: utf-8 -*-
"""Replicate vision model wrapper (phase 3 minimal implementation)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib import error, request


class ReplicateClient:
    """Thin wrapper for vision inference and key validation."""

    SUPPORTED_MODELS = {
        "llama_32_vision": "meta/llama-3.2-90b-vision",
        "qwen_vl": "qwen/qwen-vl",
        # Kept for backward compatibility in phase 3 fallback mode.
        "gpt4o_vision": "openai:gpt-4o",
    }

    def __init__(self, api_key: str = "") -> None:
        self.api_key = api_key

    def validate_key(
        self,
        api_key: str | None = None,
        *,
        check_remote: bool = False,
        timeout: float = 2.0,
    ) -> bool:
        key = (api_key if api_key is not None else self.api_key).strip()
        if not (bool(key) and (key.startswith("r8_") or key.startswith("test-"))):
            return False
        if not check_remote:
            return True
        status, _ = self._get_json(
            "https://api.replicate.com/v1/predictions",
            api_key=key,
            timeout=timeout,
        )
        return status == 200

    def check_model_availability(
        self,
        *,
        api_key: str | None = None,
        model_aliases: list[str] | None = None,
        timeout: float = 2.0,
    ) -> dict[str, dict[str, Any]]:
        """Check whether configured Replicate model aliases exist."""
        key = (api_key if api_key is not None else self.api_key).strip()
        aliases = model_aliases or list(self.SUPPORTED_MODELS.keys())
        results: dict[str, dict[str, Any]] = {}
        for alias in aliases:
            slug = self.SUPPORTED_MODELS.get(alias)
            if not slug:
                results[alias] = {"ok": False, "status": 0, "slug": None}
                continue
            if slug.startswith("openai:"):
                results[alias] = {
                    "ok": False,
                    "status": 0,
                    "slug": slug,
                    "name": None,
                    "note": "validated via OpenAI, not Replicate",
                }
                continue
            status, payload = self._get_json(
                f"https://api.replicate.com/v1/models/{slug}",
                api_key=key,
                timeout=timeout,
            )
            results[alias] = {
                "ok": status == 200,
                "status": status,
                "slug": slug,
                "name": (payload or {}).get("name") if isinstance(payload, dict) else None,
            }
        return results

    def run_vision_model(self, model_name: str, images: list[Path], prompt: str) -> str:
        """Return a mock response string in phase 3 unless a sidecar exists."""
        del prompt
        if model_name not in self.SUPPORTED_MODELS:
            raise ValueError(f"Unsupported model: {model_name}")

        for image_path in images:
            sidecar = image_path.with_suffix(image_path.suffix + ".analysis-response.json")
            if sidecar.exists():
                return sidecar.read_text(encoding="utf-8")

        return json.dumps(
            [
                {
                    "id": 1,
                    "element": "Unknown",
                    "position": {"x": 0, "y": 0},
                    "ocr_text": "",
                    "issue": "No issues inferred in fallback mode",
                    "action": "NOTE",
                    "priority": "low",
                    "reviewer_quote": "",
                }
            ]
        )

    def _get_json(self, url: str, *, api_key: str, timeout: float) -> tuple[int, dict[str, Any] | None]:
        req = request.Request(
            url,
            headers={
                "Authorization": f"Token {api_key}",
                "Content-Type": "application/json",
            },
            method="GET",
        )
        try:
            with request.urlopen(req, timeout=timeout) as response:
                status = int(getattr(response, "status", 200))
                body = response.read().decode("utf-8", errors="ignore")
                try:
                    payload = json.loads(body) if body else {}
                except json.JSONDecodeError:
                    payload = {}
                return status, payload if isinstance(payload, dict) else {}
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            try:
                payload = json.loads(body) if body else {}
            except json.JSONDecodeError:
                payload = {}
            return int(exc.code), payload if isinstance(payload, dict) else {}
        except Exception:
            return 0, None
