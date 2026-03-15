"""Ollama HTTP client helpers."""

from __future__ import annotations

import json
from typing import Any
from urllib import error, parse, request


class OllamaClientError(RuntimeError):
    """Raised when the Ollama backend cannot be reached or returns an error."""


def normalize_ollama_base_url(base_url: str | None, default_base_url: str) -> str:
    value = (base_url or default_base_url).strip()
    if not value:
        raise OllamaClientError("Ollama base URL is not configured.")
    return value.rstrip("/")


def list_ollama_models(base_url: str, timeout_seconds: float = 10.0) -> list[dict[str, Any]]:
    payload = _json_request("GET", f"{base_url}/api/tags", timeout_seconds=timeout_seconds)
    models = payload.get("models", [])
    if not isinstance(models, list):
        raise OllamaClientError("Unexpected response from Ollama while listing models.")
    normalized: list[dict[str, Any]] = []
    for item in models:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "name": item.get("name", ""),
                "size": item.get("size", 0),
                "modified_at": item.get("modified_at"),
            }
        )
    return normalized


def pull_ollama_model(
    base_url: str,
    model: str,
    timeout_seconds: float = 900.0,
) -> dict[str, Any]:
    if not model.strip():
        raise OllamaClientError("Model name is required.")
    payload = _json_request(
        "POST",
        f"{base_url}/api/pull",
        body={"name": model.strip(), "stream": False},
        timeout_seconds=timeout_seconds,
    )
    status = payload.get("status") or payload.get("message") or "completed"
    return {"status": str(status), "model": model.strip()}


def _json_request(
    method: str,
    url: str,
    *,
    body: dict[str, Any] | None = None,
    timeout_seconds: float,
) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise OllamaClientError(
            f"Ollama request failed with HTTP {exc.code}: {detail or exc.reason}"
        ) from exc
    except error.URLError as exc:
        raise OllamaClientError(f"Could not reach Ollama at {url}: {exc.reason}") from exc

    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise OllamaClientError("Ollama returned a non-JSON response.") from exc
    if not isinstance(parsed, dict):
        raise OllamaClientError("Unexpected Ollama response format.")
    return parsed
