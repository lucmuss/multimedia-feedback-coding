# -*- coding: utf-8 -*-
"""OpenAI transcription wrapper (phase 2 minimal implementation)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib import error, parse, request


class OpenAIClient:
    """Thin wrapper for transcription and key validation."""

    def __init__(self, api_key: str = "") -> None:
        self.api_key = api_key

    def validate_key(
        self,
        api_key: str | None = None,
        *,
        check_remote: bool = False,
        timeout: float = 2.0,
    ) -> bool:
        """Validate a key format and optionally verify it against the OpenAI API."""
        key = (api_key if api_key is not None else self.api_key).strip()
        if not (bool(key) and (key.startswith("sk-") or key.startswith("test-"))):
            return False
        if not check_remote:
            return True
        status, _ = self._get_json(
            "https://api.openai.com/v1/models",
            api_key=key,
            timeout=timeout,
        )
        return status == 200

    def check_model_availability(
        self,
        *,
        api_key: str | None = None,
        model_ids: list[str] | None = None,
        timeout: float = 2.0,
    ) -> dict[str, dict[str, Any]]:
        """Check if OpenAI model IDs are visible to the current API key."""
        key = (api_key if api_key is not None else self.api_key).strip()
        ids = model_ids or ["gpt-4o-transcribe", "gpt-4o"]
        results: dict[str, dict[str, Any]] = {}
        for model_id in ids:
            quoted = parse.quote(model_id, safe="")
            status, payload = self._get_json(
                f"https://api.openai.com/v1/models/{quoted}",
                api_key=key,
                timeout=timeout,
            )
            ok = status == 200
            results[model_id] = {
                "ok": ok,
                "status": status,
                "id": (payload or {}).get("id") if isinstance(payload, dict) else None,
            }
        return results

    def transcribe(self, audio_path: Path, language: str = "de") -> dict[str, Any]:
        """Send audio to OpenAI whisper-1 API and return transcription with segments.
        
        If a sidecar `<audio>.transcript.json` exists, it will use it (phase 2), 
        otherwise performs a real network multipart POST.
        """
        sidecar = audio_path.with_suffix(audio_path.suffix + ".transcript.json")
        if sidecar.exists():
            data = json.loads(sidecar.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data

        if not self.api_key:
            raise ValueError("OpenAI API key is missing. Set it in Settings.")

        import uuid
        import mimetypes

        boundary = uuid.uuid4().hex
        fields = {
            "model": "whisper-1",
            "language": language[:2].lower(),
            "response_format": "verbose_json",
        }
        
        body_parts = []
        for key, value in fields.items():
            body_parts.append(f"--{boundary}\r\n".encode("utf-8"))
            body_parts.append(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8"))
            body_parts.append(f"{value}\r\n".encode("utf-8"))

        filename = audio_path.name
        mimetype = mimetypes.guess_type(filename)[0] or "audio/wav"
        body_parts.append(f"--{boundary}\r\n".encode("utf-8"))
        body_parts.append(f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode("utf-8"))
        body_parts.append(f"Content-Type: {mimetype}\r\n\r\n".encode("utf-8"))
        body_parts.append(audio_path.read_bytes())
        body_parts.append(b"\r\n")
        body_parts.append(f"--{boundary}--\r\n".encode("utf-8"))
        
        payload = b"".join(body_parts)

        req = request.Request(
            "https://api.openai.com/v1/audio/transcriptions",
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            method="POST",
        )
        
        try:
            with request.urlopen(req, timeout=45.0) as response:
                body = response.read().decode("utf-8", errors="ignore")
                try:
                    res_json = json.loads(body)
                except json.JSONDecodeError:
                    raise ValueError(f"OpenAI API non-JSON response: {body[:200]}")
                return {
                    "text": res_json.get("text", ""),
                    "segments": res_json.get("segments", []),
                    "provider": "openai:whisper-1",
                    "language": language,
                }
        except error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="ignore")
            raise ValueError(f"OpenAI API error {exc.code}: {err_body}")

    def _get_json(self, url: str, *, api_key: str, timeout: float) -> tuple[int, dict[str, Any] | None]:
        req = request.Request(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
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
