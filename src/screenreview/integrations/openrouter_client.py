# -*- coding: utf-8 -*-
"""OpenRouter vision model wrapper with OpenAI-compatible payloads."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib import error, request

from screenreview.utils.image_utils import encode_file_base64


class OpenRouterClient:
    """Thin wrapper for OpenRouter model checks and vision inference."""

    SUPPORTED_MODELS = {
        # OpenRouter availability can differ from Replicate; 11B is the compatible fallback alias.
        "llama_32_vision": "meta-llama/llama-3.2-11b-vision-instruct",
        "qwen_vl": "qwen/qwen2.5-vl-72b-instruct",
        "gpt4o_vision": "openai/gpt-4o",
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
        """Validate key format and optionally test against model listing."""
        key = (api_key if api_key is not None else self.api_key).strip()
        if not (bool(key) and (key.startswith("sk-or-v1-") or key.startswith("test-"))):
            return False
        if not check_remote:
            return True
        status, _ = self._request_json(
            "GET",
            "https://openrouter.ai/api/v1/models",
            api_key=key,
            timeout=timeout,
        )
        return status == 200

    def check_model_availability(
        self,
        *,
        api_key: str | None = None,
        model_aliases: list[str] | None = None,
        timeout: float = 3.0,
    ) -> dict[str, dict[str, Any]]:
        """Check if aliased models appear in OpenRouter's model index."""
        key = (api_key if api_key is not None else self.api_key).strip()
        aliases = model_aliases or list(self.SUPPORTED_MODELS.keys())
        status, payload = self._request_json(
            "GET",
            "https://openrouter.ai/api/v1/models",
            api_key=key,
            timeout=timeout,
        )
        records = payload.get("data", []) if isinstance(payload, dict) else []
        model_ids = {
            str(item.get("id", ""))
            for item in records
            if isinstance(item, dict) and item.get("id")
        }
        results: dict[str, dict[str, Any]] = {}
        for alias in aliases:
            routed_id = self.SUPPORTED_MODELS.get(alias)
            if not routed_id:
                results[alias] = {"ok": False, "status": status, "model_id": None}
                continue
            results[alias] = {
                "ok": status == 200 and routed_id in model_ids,
                "status": status,
                "model_id": routed_id,
            }
        return results

    def run_vision_model(self, model_name: str, images: list[Path], prompt: str) -> str:
        """Run a vision analysis request or fallback to local sidecar response."""
        routed_model = self.SUPPORTED_MODELS.get(model_name)
        if not routed_model:
            raise ValueError(f"Unsupported model: {model_name}")

        for image_path in images:
            sidecar = image_path.with_suffix(image_path.suffix + ".analysis-response.json")
            if sidecar.exists():
                return sidecar.read_text(encoding="utf-8")

        if not self.validate_key(check_remote=False):
            raise ValueError("OpenRouter API key missing or invalid format")

        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        for image_path in images:
            mime = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"
            b64 = encode_file_base64(image_path)
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{b64}"},
                }
            )

        payload = {
            "model": routed_model,
            "messages": [{"role": "user", "content": content}],
            "temperature": 0.1,
        }
        status, response_payload = self._request_json(
            "POST",
            "https://openrouter.ai/api/v1/chat/completions",
            api_key=self.api_key,
            timeout=30.0,
            data=payload,
        )
        if status != 200 or not isinstance(response_payload, dict):
            raise RuntimeError(f"OpenRouter request failed (status={status})")

        choices = response_payload.get("choices", [])
        if not isinstance(choices, list) or not choices:
            raise RuntimeError("OpenRouter response has no choices")
        message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
        content_value = message.get("content", "") if isinstance(message, dict) else ""
        if isinstance(content_value, str):
            return content_value
        if isinstance(content_value, list):
            text_parts = []
            for item in content_value:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(str(item.get("text", "")))
            return "\n".join(part for part in text_parts if part)
        return str(content_value)

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        api_key: str,
        timeout: float,
        data: dict[str, Any] | None = None,
    ) -> tuple[int, dict[str, Any] | None]:
        body = None
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        if data is not None:
            body = json.dumps(data).encode("utf-8")
        req = request.Request(url, headers=headers, data=body, method=method)
        try:
            with request.urlopen(req, timeout=timeout) as response:
                status = int(getattr(response, "status", 200))
                raw_body = response.read().decode("utf-8", errors="ignore")
                try:
                    payload = json.loads(raw_body) if raw_body else {}
                except json.JSONDecodeError:
                    payload = {}
                return status, payload if isinstance(payload, dict) else {}
        except error.HTTPError as exc:
            raw_body = exc.read().decode("utf-8", errors="ignore")
            try:
                payload = json.loads(raw_body) if raw_body else {}
            except json.JSONDecodeError:
                payload = {}
            return int(exc.code), payload if isinstance(payload, dict) else {}
        except Exception:
            return 0, None
