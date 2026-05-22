"""
Ingestion Pipeline API
======================
Receives inference logs from the SDK, validates them,
applies PII redaction, and persists via the event bus.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.base import get_db
from app.models.conversation import InferenceLog, Conversation
from app.schemas.conversation import IngestLogPayload, InferenceLogOut
from app.events.bus import bus
from app.core.pii import redact

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ingest", tags=["ingestion"])


async def _persist_log(payload: dict, db: AsyncSession):
    """Validate conversation exists, redact PII, write to DB."""
    # Validate conversation exists
    result = await db.execute(
        select(Conversation).where(Conversation.id == payload["conversation_id"])
    )
    conv = result.scalar_one_or_none()
    if not conv:
        logger.warning(f"Ingest: unknown conversation_id {payload['conversation_id']}")
        return

    log = InferenceLog(
        conversation_id=payload["conversation_id"],
        provider=payload["provider"],
        model=payload["model"],
        started_at=payload["started_at"],
        ended_at=payload.get("ended_at"),
        latency_ms=payload.get("latency_ms"),
        prompt_tokens=payload.get("prompt_tokens"),
        completion_tokens=payload.get("completion_tokens"),
        total_tokens=payload.get("total_tokens"),
        status=payload.get("status", "success"),
        error_message=payload.get("error_message"),
        http_status_code=payload.get("http_status_code"),
        input_preview=redact(payload.get("input_preview") or ""),
        output_preview=redact(payload.get("output_preview") or ""),
        is_streaming=payload.get("is_streaming", False),
        extra_metadata=payload.get("metadata"),
    )
    db.add(log)
    await db.flush()
    logger.debug(f"Ingested log {log.id} for conversation {log.conversation_id}")


@router.post("/log", status_code=202)
async def ingest_log(
    payload: IngestLogPayload,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Receive a single inference log from the SDK.
    Validates payload, publishes to event bus for async processing.
    Returns 202 immediately — never blocks the LLM response path.
    """
    try:
        data = payload.model_dump()
        # Publish to event bus (async, non-blocking)
        await bus.publish("inference_log", data)
        return {"status": "accepted", "conversation_id": str(payload.conversation_id)}
    except Exception as exc:
        logger.error(f"Ingest error: {exc}")
        raise HTTPException(status_code=500, detail="Ingestion failed")


@router.post("/log/batch", status_code=202)
async def ingest_log_batch(
    payloads: list[IngestLogPayload],
    db: AsyncSession = Depends(get_db),
):
    """Batch ingestion endpoint for bulk log shipping."""
    if len(payloads) > 500:
        raise HTTPException(status_code=400, detail="Batch size exceeds 500")
    for payload in payloads:
        await bus.publish("inference_log", payload.model_dump())
    return {"status": "accepted", "count": len(payloads)}
