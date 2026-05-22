"""
Data models for the SDK.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any


@dataclass
class InferenceMetadata:
    """Captured metadata for a single LLM inference call."""
    log_id: str
    conversation_id: str
    provider: str
    model: str
    started_at: datetime
    ended_at: Optional[datetime]
    latency_ms: float
    prompt_tokens: Optional[int]
    completion_tokens: Optional[int]
    total_tokens: Optional[int]
    status: str                    # "success" | "error" | "timeout"
    error_message: Optional[str]
    http_status_code: int
    input_preview: str             # truncated + PII-redacted
    output_preview: str            # truncated + PII-redacted
    is_streaming: bool
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "conversation_id": self.conversation_id,
            "provider": self.provider,
            "model": self.model,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "latency_ms": self.latency_ms,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "status": self.status,
            "error_message": self.error_message,
            "http_status_code": self.http_status_code,
            "input_preview": self.input_preview,
            "output_preview": self.output_preview,
            "is_streaming": self.is_streaming,
            "extra_metadata": {"log_id": self.log_id, "sdk_version": "1.0.0", **self.extra},
        }
