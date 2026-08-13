"""LLM summarization — OpenRouter + local backends (streaming)."""
from __future__ import annotations

from collections.abc import AsyncIterator

import httpx

# OpenRouter default (used when no explicit base_url is given).
_DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


class SummarizationError(RuntimeError):
    """Raised when the summarization call fails."""


def _build_headers(api_key: str) -> dict[str, str]:
    """Build request headers. Skips Authorization for local backends (empty key)."""
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


async def summarize(
    transcript: str,
    prompt: str,
    model: str,
    api_key: str = "",
    base_url: str = "",
    temperature: float = 0.3,
) -> AsyncIterator[str]:
    """Stream a summary, yielding content chunks.

    Works with OpenRouter, Ollama, llama.cpp server, LM Studio, and any
    OpenAI-compatible endpoint.  Leave *api_key* empty for local backends
    that don't require authentication.
    """
    base_url = base_url or _DEFAULT_BASE_URL
    url = f"{base_url}/chat/completions"
    headers = _build_headers(api_key)
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": transcript},
        ],
        "temperature": temperature,
        "stream": True,
    }

    async with httpx.AsyncClient(timeout=300.0) as client:
        try:
            async with client.stream("POST", url, headers=headers, json=body) as resp:
                if resp.status_code != 200:
                    text = await resp.aread()
                    raise SummarizationError(
                        f"HTTP {resp.status_code}: {text[:300]!r}"
                    )
                yielded = False
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    import json

                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    choices = chunk.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    content = delta.get("content")
                    if content:
                        yielded = True
                        yield content
                if not yielded:
                    async for piece in _summarize_once(
                        transcript, prompt, model, api_key, base_url, temperature
                    ):
                        yield piece
        except (httpx.HTTPError, SummarizationError):
            async for piece in _summarize_once(
                transcript, prompt, model, api_key, base_url, temperature
            ):
                yield piece


async def _summarize_once(
    transcript: str,
    prompt: str,
    model: str,
    api_key: str,
    base_url: str,
    temperature: float,
) -> AsyncIterator[str]:
    """Single non-streaming request; yields full content as one chunk."""
    url = f"{base_url}/chat/completions"
    headers = _build_headers(api_key)
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": transcript},
        ],
        "temperature": temperature,
        "stream": False,
    }
    async with httpx.AsyncClient(timeout=300.0) as client:
        resp = await client.post(url, headers=headers, json=body)
        if resp.status_code != 200:
            raise SummarizationError(
                f"HTTP {resp.status_code}: {resp.text[:300]!r}"
            )
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        if content:
            yield content


async def summarize_text(
    transcript: str,
    prompt: str,
    model: str,
    api_key: str = "",
    base_url: str = "",
    temperature: float = 0.3,
) -> str:
    """Convenience: gather the streamed summary into a single string."""
    chunks: list[str] = []
    async for chunk in summarize(transcript, prompt, model, api_key, base_url, temperature):
        chunks.append(chunk)
    return "".join(chunks)