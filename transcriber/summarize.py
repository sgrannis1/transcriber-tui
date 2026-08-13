"""LLM summarization via OpenRouter (streaming)."""
from __future__ import annotations

from collections.abc import AsyncIterator

import httpx

BASE_URL = "https://openrouter.ai/api/v1/chat/completions"


class SummarizationError(RuntimeError):
    """Raised when the OpenRouter call fails."""


async def summarize(
    transcript: str,
    prompt: str,
    model: str,
    api_key: str,
    temperature: float = 0.3,
) -> AsyncIterator[str]:
    """Stream a summary from OpenRouter, yielding content chunks.

    Falls back to a single non-streaming request if streaming is rejected
    or fails mid-stream.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": transcript},
        ],
        "temperature": temperature,
        "stream": True,
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            async with client.stream("POST", BASE_URL, headers=headers, json=body) as resp:
                if resp.status_code != 200:
                    text = await resp.aread()
                    raise SummarizationError(
                        f"OpenRouter HTTP {resp.status_code}: {text[:300]!r}"
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
                    # Streaming produced no tokens; fall back to non-streaming.
                    async for piece in _summarize_once(
                        transcript, prompt, model, api_key, temperature
                    ):
                        yield piece
        except (httpx.HTTPError, SummarizationError):
            # Fall back to a single-shot request on any transport failure.
            async for piece in _summarize_once(
                transcript, prompt, model, api_key, temperature
            ):
                yield piece


async def _summarize_once(
    transcript: str,
    prompt: str,
    model: str,
    api_key: str,
    temperature: float,
) -> AsyncIterator[str]:
    """Single non-streaming request; yields the full content as one chunk."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": transcript},
        ],
        "temperature": temperature,
        "stream": False,
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(BASE_URL, headers=headers, json=body)
        if resp.status_code != 200:
            raise SummarizationError(
                f"OpenRouter HTTP {resp.status_code}: {resp.text[:300]!r}"
            )
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        if content:
            yield content


async def summarize_text(
    transcript: str,
    prompt: str,
    model: str,
    api_key: str,
    temperature: float = 0.3,
) -> str:
    """Convenience: gather the streamed summary into a single string."""
    chunks: list[str] = []
    async for chunk in summarize(transcript, prompt, model, api_key, temperature):
        chunks.append(chunk)
    return "".join(chunks)