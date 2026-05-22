"""
LLMLogger — the main SDK client.
"""
import asyncio
import time
import uuid
import logging
from datetime import datetime, timezone
from typing import AsyncIterator, List, Dict, Any, Optional

import httpx
from openai import AsyncOpenAI

from .models import InferenceMetadata
from .pii import redact

logger = logging.getLogger("ollive_sdk")

PROVIDER_DEFAULTS = {
    "groq":       {"base_url": "https://api.groq.com/openai/v1",    "model": "llama3-8b-8192"},
    "ollama":     {"base_url": "http://localhost:11434/v1",          "model": "llama3"},
    "openai":     {"base_url": "https://api.openai.com/v1",         "model": "gpt-4o-mini"},
    "openrouter": {"base_url": "https://openrouter.ai/api/v1",      "model": "mistralai/mistral-7b-instruct:free"},
}


class LLMLogger:
    """
    Drop-in LLM wrapper with automatic inference logging.

    Parameters
    ----------
    provider : str
        One of: groq, ollama, openai, openrouter
    model : str
        Model ID for the provider
    api_key : str
        Provider API key (not needed for ollama)
    ingestion_url : str
        URL of the Ollive ingestion endpoint
    preview_length : int
        Max characters to capture in input/output previews
    redact_pii : bool
        Whether to redact PII from previews before logging
    """

    def __init__(
        self,
        provider: str = "groq",
        model: Optional[str] = None,
        api_key: str = "no-key",
        base_url: Optional[str] = None,
        ingestion_url: str = "http://localhost:8000/api/v1/ingest/log",
        preview_length: int = 300,
        redact_pii: bool = True,
    ):
        self.provider = provider
        defaults = PROVIDER_DEFAULTS.get(provider, {})
        self.model = model or defaults.get("model", "unknown")
        self.ingestion_url = ingestion_url
        self.preview_length = preview_length
        self.redact_pii = redact_pii

        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url or defaults.get("base_url", "https://api.openai.com/v1"),
            timeout=60.0,
        )

    def _make_preview(self, text: str) -> str:
        truncated = text[:self.preview_length] + ("…" if len(text) > self.preview_length else "")
        return redact(truncated) if self.redact_pii else truncated

    async def chat(
        self,
        conversation_id: str,
        messages: List[Dict[str, str]],
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Non-streaming chat. Returns dict with 'content', 'usage', 'metadata'.
        """
        log_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc)
        t0 = time.perf_counter()
        status = "success"
        error_msg = None
        content = ""
        usage: Dict[str, Any] = {}

        try:
            completion = await self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=False,
                **kwargs,
            )
            content = completion.choices[0].message.content or ""
            if completion.usage:
                usage = {
                    "prompt_tokens": completion.usage.prompt_tokens,
                    "completion_tokens": completion.usage.completion_tokens,
                    "total_tokens": completion.usage.total_tokens,
                }
        except Exception as exc:
            status = "error"
            error_msg = str(exc)
            raise

        finally:
            latency_ms = (time.perf_counter() - t0) * 1000
            ended_at = datetime.now(timezone.utc)
            meta = InferenceMetadata(
                log_id=log_id,
                conversation_id=conversation_id,
                provider=self.provider,
                model=self.model,
                started_at=started_at,
                ended_at=ended_at,
                latency_ms=round(latency_ms, 2),
                prompt_tokens=usage.get("prompt_tokens"),
                completion_tokens=usage.get("completion_tokens"),
                total_tokens=usage.get("total_tokens"),
                status=status,
                error_message=error_msg,
                http_status_code=200 if status == "success" else 500,
                input_preview=self._make_preview(messages[-1]["content"] if messages else ""),
                output_preview=self._make_preview(content),
                is_streaming=False,
            )
            asyncio.create_task(self._ship_log(meta))

        return {"content": content, "usage": usage, "log_id": log_id, "latency_ms": round(latency_ms, 2)}

    async def stream(
        self,
        conversation_id: str,
        messages: List[Dict[str, str]],
        **kwargs,
    ) -> AsyncIterator[str]:
        """Streaming chat — yields text chunks, logs after completion."""
        log_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc)
        t0 = time.perf_counter()
        status = "success"
        error_msg = None
        full_response: List[str] = []
        prompt_tokens = completion_tokens = total_tokens = None

        try:
            stream_obj = await self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
                stream_options={"include_usage": True},
                **kwargs,
            )
            async for chunk in stream_obj:
                if chunk.choices and chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    full_response.append(token)
                    yield token
                if hasattr(chunk, "usage") and chunk.usage:
                    prompt_tokens = chunk.usage.prompt_tokens
                    completion_tokens = chunk.usage.completion_tokens
                    total_tokens = chunk.usage.total_tokens
        except Exception as exc:
            status = "error"
            error_msg = str(exc)
            raise
        finally:
            latency_ms = (time.perf_counter() - t0) * 1000
            meta = InferenceMetadata(
                log_id=log_id,
                conversation_id=conversation_id,
                provider=self.provider,
                model=self.model,
                started_at=started_at,
                ended_at=datetime.now(timezone.utc),
                latency_ms=round(latency_ms, 2),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                status=status,
                error_message=error_msg,
                http_status_code=200 if status == "success" else 500,
                input_preview=self._make_preview(messages[-1]["content"] if messages else ""),
                output_preview=self._make_preview("".join(full_response)),
                is_streaming=True,
            )
            asyncio.create_task(self._ship_log(meta))

    async def _ship_log(self, meta: InferenceMetadata):
        """Fire-and-forget log shipping to ingestion endpoint."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(self.ingestion_url, json=meta.to_dict())
        except Exception as exc:
            logger.debug(f"Log shipping failed (non-critical): {exc}")
