"""
Ollive LLM SDK
==============
A lightweight wrapper around multiple LLM providers that:
  - Abstracts provider differences behind a unified interface
  - Captures inference metadata (latency, tokens, status, previews)
  - Sends logs to the ingestion endpoint asynchronously (fire-and-forget)
  - Supports streaming responses
  - Redacts PII from previews before logging

Supported providers:
  - groq      (free tier — llama3, mixtral, gemma)
  - ollama    (fully local — llama3, mistral, phi3, etc.)
  - openai    (gpt-4o-mini, gpt-3.5-turbo)
  - openrouter (free models — mistral, llama, etc.)
"""
import asyncio
import time
import uuid
from datetime import datetime
from typing import AsyncIterator, List, Optional, Dict, Any

import httpx
from openai import AsyncOpenAI

from app.core.config import settings
from app.core.pii import redact


# ── Provider registry ─────────────────────────────────────────────────────────

PROVIDERS: Dict[str, Dict[str, Any]] = {
    "groq": {
        "base_url": settings.GROQ_BASE_URL,
        "api_key_env": settings.GROQ_API_KEY,
        "default_model": "llama3-8b-8192",
        "free": True,
    },
    "ollama": {
        "base_url": f"{settings.OLLAMA_BASE_URL}/v1",
        "api_key_env": "ollama",   # ollama doesn't need a real key
        "default_model": "llama3",
        "free": True,
    },
    "openai": {
        "base_url": settings.OPENAI_BASE_URL,
        "api_key_env": settings.OPENAI_API_KEY,
        "default_model": "gpt-4o-mini",
        "free": False,
    },
    "openrouter": {
        "base_url": settings.OPENROUTER_BASE_URL,
        "api_key_env": settings.OPENROUTER_API_KEY,
        "default_model": "mistralai/mistral-7b-instruct:free",
        "free": True,
    },
}


def _get_client(provider: str) -> AsyncOpenAI:
    """Return an AsyncOpenAI client pointed at the right provider base URL."""
    cfg = PROVIDERS.get(provider)
    if not cfg:
        raise ValueError(f"Unknown provider: {provider}. Available: {list(PROVIDERS.keys())}")
    return AsyncOpenAI(
        api_key=cfg["api_key_env"] or "no-key",
        base_url=cfg["base_url"],
        timeout=60.0,
    )


def _preview(text: str, max_len: int = 300) -> str:
    """Truncate + redact PII for safe storage."""
    if not text:
        return ""
    truncated = text[:max_len] + ("…" if len(text) > max_len else "")
    return redact(truncated)


# ── Core SDK class ────────────────────────────────────────────────────────────

class LLMClient:
    """
    Unified LLM client with built-in observability.

    Usage:
        client = LLMClient(provider="groq", model="llama3-8b-8192")
        response = await client.chat(conversation_id, messages)
    """

    def __init__(
        self,
        provider: str = settings.DEFAULT_PROVIDER,
        model: str = settings.DEFAULT_MODEL,
        ingestion_url: str = "http://localhost:8000/api/v1/ingest/log",
    ):
        self.provider = provider
        self.model = model
        self.ingestion_url = ingestion_url
        self._client = _get_client(provider)

    async def chat(
        self,
        conversation_id: uuid.UUID,
        messages: List[Dict[str, str]],
        stream: bool = False,
    ) -> Dict[str, Any]:
        """
        Non-streaming chat completion.
        Returns: {"content": str, "usage": {...}, "log_id": str}
        """
        started_at = datetime.utcnow()
        t0 = time.perf_counter()
        log_id = str(uuid.uuid4())
        status = "success"
        error_msg = None
        response_content = ""
        usage = {}
        http_status = 200

        try:
            completion = await self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=False,
            )
            response_content = completion.choices[0].message.content or ""
            usage = {
                "prompt_tokens": completion.usage.prompt_tokens if completion.usage else None,
                "completion_tokens": completion.usage.completion_tokens if completion.usage else None,
                "total_tokens": completion.usage.total_tokens if completion.usage else None,
            }
        except Exception as exc:
            status = "error"
            error_msg = str(exc)
            http_status = 500

        latency_ms = (time.perf_counter() - t0) * 1000
        ended_at = datetime.utcnow()

        # Fire-and-forget log ingestion
        asyncio.create_task(
            self._send_log(
                log_id=log_id,
                conversation_id=str(conversation_id),
                started_at=started_at.isoformat(),
                ended_at=ended_at.isoformat(),
                latency_ms=round(latency_ms, 2),
                status=status,
                error_message=error_msg,
                http_status_code=http_status,
                input_preview=_preview(messages[-1]["content"] if messages else ""),
                output_preview=_preview(response_content),
                is_streaming=False,
                **usage,
            )
        )

        if status == "error":
            raise RuntimeError(error_msg)

        return {
            "content": response_content,
            "usage": usage,
            "log_id": log_id,
            "latency_ms": round(latency_ms, 2),
        }

    async def chat_stream(
        self,
        conversation_id: uuid.UUID,
        messages: List[Dict[str, str]],
    ) -> AsyncIterator[str]:
        """
        Streaming chat completion — yields text chunks.
        Logs metadata after stream completes.
        """
        started_at = datetime.utcnow()
        t0 = time.perf_counter()
        log_id = str(uuid.uuid4())
        status = "success"
        error_msg = None
        full_response = []
        prompt_tokens = None
        completion_tokens = None
        total_tokens = None

        try:
            stream = await self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
                stream_options={"include_usage": True},
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    full_response.append(token)
                    yield token
                # Capture usage from final chunk (OpenAI-compatible)
                if hasattr(chunk, "usage") and chunk.usage:
                    prompt_tokens = chunk.usage.prompt_tokens
                    completion_tokens = chunk.usage.completion_tokens
                    total_tokens = chunk.usage.total_tokens

        except Exception as exc:
            status = "error"
            error_msg = str(exc)
            yield f"\n\n[ERROR: {exc}]"

        latency_ms = (time.perf_counter() - t0) * 1000
        ended_at = datetime.utcnow()

        asyncio.create_task(
            self._send_log(
                log_id=log_id,
                conversation_id=str(conversation_id),
                started_at=started_at.isoformat(),
                ended_at=ended_at.isoformat(),
                latency_ms=round(latency_ms, 2),
                status=status,
                error_message=error_msg,
                http_status_code=200 if status == "success" else 500,
                input_preview=_preview(messages[-1]["content"] if messages else ""),
                output_preview=_preview("".join(full_response)),
                is_streaming=True,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            )
        )

    async def _send_log(
        self,
        log_id: str,
        conversation_id: str,
        started_at: str,
        ended_at: str,
        latency_ms: float,
        status: str,
        error_message: Optional[str],
        http_status_code: int,
        input_preview: str,
        output_preview: str,
        is_streaming: bool,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        total_tokens: Optional[int] = None,
    ):
        """Send inference log to ingestion endpoint (non-blocking)."""
        payload = {
            "conversation_id": conversation_id,
            "provider": self.provider,
            "model": self.model,
            "started_at": started_at,
            "ended_at": ended_at,
            "latency_ms": latency_ms,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "status": status,
            "error_message": error_message,
            "http_status_code": http_status_code,
            "input_preview": input_preview,
            "output_preview": output_preview,
            "is_streaming": is_streaming,
            "extra_metadata": {"log_id": log_id, "sdk_version": "1.0.0"},
        }
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(self.ingestion_url, json=payload)
        except Exception:
            # Never let logging failures affect the main request
            pass
