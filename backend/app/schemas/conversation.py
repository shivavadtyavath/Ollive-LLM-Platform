"""
Pydantic schemas for request/response validation.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from enum import Enum


class ConversationStatus(str, Enum):
    active = "active"
    cancelled = "cancelled"
    archived = "archived"


class MessageRole(str, Enum):
    user = "user"
    assistant = "assistant"
    system = "system"


# ── Message ──────────────────────────────────────────────────────────────────

class MessageBase(BaseModel):
    role: MessageRole
    content: str


class MessageCreate(BaseModel):
    content: str
    provider: Optional[str] = None
    model: Optional[str] = None
    stream: bool = False


class MessageOut(MessageBase):
    id: UUID
    conversation_id: UUID
    token_count: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ── Conversation ──────────────────────────────────────────────────────────────

class ConversationCreate(BaseModel):
    title: Optional[str] = None
    provider: Optional[str] = "groq"
    model: Optional[str] = "llama3-8b-8192"


class ConversationOut(BaseModel):
    id: UUID
    title: Optional[str]
    status: ConversationStatus
    provider: str
    model: str
    created_at: datetime
    updated_at: datetime
    message_count: Optional[int] = 0

    class Config:
        from_attributes = True


class ConversationDetail(ConversationOut):
    messages: List[MessageOut] = []


# ── Inference Log ─────────────────────────────────────────────────────────────

class InferenceLogOut(BaseModel):
    id: UUID
    conversation_id: UUID
    provider: str
    model: str
    started_at: datetime
    ended_at: Optional[datetime]
    latency_ms: Optional[float]
    prompt_tokens: Optional[int]
    completion_tokens: Optional[int]
    total_tokens: Optional[int]
    status: str
    error_message: Optional[str]
    input_preview: Optional[str]
    output_preview: Optional[str]
    is_streaming: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ── Ingestion ─────────────────────────────────────────────────────────────────

class IngestLogPayload(BaseModel):
    conversation_id: UUID
    provider: str
    model: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    latency_ms: Optional[float] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    status: str = "success"
    error_message: Optional[str] = None
    http_status_code: Optional[int] = None
    input_preview: Optional[str] = None
    output_preview: Optional[str] = None
    is_streaming: bool = False
    extra_metadata: Optional[dict] = None


# ── Dashboard / Metrics ───────────────────────────────────────────────────────

class MetricsSummary(BaseModel):
    total_requests: int
    success_count: int
    error_count: int
    avg_latency_ms: Optional[float]
    p95_latency_ms: Optional[float]
    total_tokens: Optional[int]
    requests_per_provider: dict
    requests_per_model: dict
    error_rate: float


class LatencyBucket(BaseModel):
    timestamp: str
    avg_latency_ms: float
    request_count: int


class ProviderStats(BaseModel):
    provider: str
    model: str
    total_requests: int
    success_rate: float
    avg_latency_ms: float
    total_tokens: int
