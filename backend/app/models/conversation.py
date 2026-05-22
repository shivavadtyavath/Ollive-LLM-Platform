"""
Database models — Conversations, Messages, InferenceLogs.
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Text, Integer, Float, Boolean,
    DateTime, ForeignKey, Enum as SAEnum, JSON
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base
import enum


class ConversationStatus(str, enum.Enum):
    active = "active"
    cancelled = "cancelled"
    archived = "archived"


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=True)
    status = Column(SAEnum(ConversationStatus), default=ConversationStatus.active, nullable=False)
    provider = Column(String(64), nullable=False, default="groq")
    model = Column(String(128), nullable=False, default="llama3-8b-8192")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")
    inference_logs = relationship("InferenceLog", back_populates="conversation", cascade="all, delete-orphan")


class MessageRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"
    system = "system"


class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role = Column(SAEnum(MessageRole), nullable=False)
    content = Column(Text, nullable=False)
    content_redacted = Column(Text, nullable=True)   # PII-redacted copy
    token_count = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    conversation = relationship("Conversation", back_populates="messages")


class InferenceLog(Base):
    __tablename__ = "inference_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)

    # Provider / model info
    provider = Column(String(64), nullable=False)
    model = Column(String(128), nullable=False)

    # Timing
    started_at = Column(DateTime, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    latency_ms = Column(Float, nullable=True)

    # Token usage
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)

    # Status
    status = Column(String(32), nullable=False, default="success")  # success | error | timeout
    error_message = Column(Text, nullable=True)
    http_status_code = Column(Integer, nullable=True)

    # Previews (truncated, PII-redacted)
    input_preview = Column(Text, nullable=True)
    output_preview = Column(Text, nullable=True)

    # Streaming flag
    is_streaming = Column(Boolean, default=False)

    # Raw metadata blob (flexible)
    extra_metadata = Column("metadata", JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    conversation = relationship("Conversation", back_populates="inference_logs")
