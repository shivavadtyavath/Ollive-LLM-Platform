"""
Ollive LLM SDK
==============
Standalone Python SDK for wrapping LLM calls with automatic
inference logging. Can be used independently of the platform.

Usage:
    from ollive_sdk import LLMLogger

    logger = LLMLogger(
        provider="groq",
        model="llama3-8b-8192",
        api_key="your-key",
        ingestion_url="http://your-server/api/v1/ingest/log",
    )

    response = await logger.chat(
        conversation_id="session-123",
        messages=[{"role": "user", "content": "Hello!"}],
    )
"""
from .client import LLMLogger
from .models import InferenceMetadata

__all__ = ["LLMLogger", "InferenceMetadata"]
__version__ = "1.0.0"
