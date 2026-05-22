"""
Conversation CRUD + chat endpoints.
"""
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from sqlalchemy.orm import selectinload

from app.db.base import get_db
from app.models.conversation import Conversation, Message, ConversationStatus, MessageRole
from app.schemas.conversation import (
    ConversationCreate, ConversationOut, ConversationDetail,
    MessageCreate, MessageOut,
)
from app.sdk.llm_sdk import LLMClient
from app.core.config import settings
from app.core.pii import redact

router = APIRouter(prefix="/conversations", tags=["conversations"])


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_conversation_or_404(conv_id: uuid.UUID, db: AsyncSession) -> Conversation:
    result = await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(Conversation.id == conv_id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


def _build_messages_for_llm(messages: list, max_context: int = settings.MAX_CONTEXT_MESSAGES) -> list:
    """Convert DB messages to OpenAI-compatible format, keeping last N."""
    recent = messages[-max_context:]
    return [{"role": m.role.value, "content": m.content} for m in recent]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("", response_model=ConversationOut, status_code=201)
async def create_conversation(
    body: ConversationCreate,
    db: AsyncSession = Depends(get_db),
):
    conv = Conversation(
        title=body.title or "New conversation",
        provider=body.provider or settings.DEFAULT_PROVIDER,
        model=body.model or settings.DEFAULT_MODEL,
    )
    db.add(conv)
    await db.flush()
    await db.refresh(conv)
    result = ConversationOut(
        id=conv.id,
        title=conv.title,
        status=conv.status,
        provider=conv.provider,
        model=conv.model,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        message_count=0,
    )
    return result


@router.get("", response_model=List[ConversationOut])
async def list_conversations(
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
):
    q = select(Conversation)
    if status:
        q = q.where(Conversation.status == status)
    q = q.order_by(Conversation.updated_at.desc()).limit(limit).offset(offset)
    result = await db.execute(q)
    convs = result.scalars().all()

    # Get message counts
    out = []
    for conv in convs:
        count_result = await db.execute(
            select(func.count(Message.id)).where(Message.conversation_id == conv.id)
        )
        count = count_result.scalar() or 0
        out.append(ConversationOut(
            id=conv.id,
            title=conv.title,
            status=conv.status,
            provider=conv.provider,
            model=conv.model,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            message_count=count,
        ))
    return out


@router.get("/{conv_id}", response_model=ConversationDetail)
async def get_conversation(
    conv_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    conv = await _get_conversation_or_404(conv_id, db)
    return ConversationDetail(
        id=conv.id,
        title=conv.title,
        status=conv.status,
        provider=conv.provider,
        model=conv.model,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        message_count=len(conv.messages),
        messages=[
            MessageOut(
                id=m.id,
                conversation_id=m.conversation_id,
                role=m.role,
                content=m.content,
                token_count=m.token_count,
                created_at=m.created_at,
            )
            for m in conv.messages
        ],
    )


@router.post("/{conv_id}/cancel", response_model=ConversationOut)
async def cancel_conversation(
    conv_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    conv = await _get_conversation_or_404(conv_id, db)
    if conv.status == ConversationStatus.cancelled:
        raise HTTPException(status_code=400, detail="Already cancelled")
    conv.status = ConversationStatus.cancelled
    await db.flush()
    await db.refresh(conv)
    return ConversationOut(
        id=conv.id, title=conv.title, status=conv.status,
        provider=conv.provider, model=conv.model,
        created_at=conv.created_at, updated_at=conv.updated_at,
    )


@router.post("/{conv_id}/resume", response_model=ConversationOut)
async def resume_conversation(
    conv_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    conv = await _get_conversation_or_404(conv_id, db)
    conv.status = ConversationStatus.active
    await db.flush()
    await db.refresh(conv)
    return ConversationOut(
        id=conv.id, title=conv.title, status=conv.status,
        provider=conv.provider, model=conv.model,
        created_at=conv.created_at, updated_at=conv.updated_at,
    )


@router.delete("/{conv_id}", status_code=204)
async def delete_conversation(
    conv_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    conv = await _get_conversation_or_404(conv_id, db)
    await db.delete(conv)


@router.post("/{conv_id}/messages", response_model=MessageOut)
async def send_message(
    conv_id: uuid.UUID,
    body: MessageCreate,
    db: AsyncSession = Depends(get_db),
):
    """Non-streaming chat turn."""
    conv = await _get_conversation_or_404(conv_id, db)
    if conv.status == ConversationStatus.cancelled:
        raise HTTPException(status_code=400, detail="Conversation is cancelled. Resume it first.")

    # Override provider/model if requested
    provider = body.provider or conv.provider
    model = body.model or conv.model

    # Save user message
    user_msg = Message(
        conversation_id=conv_id,
        role=MessageRole.user,
        content=body.content,
        content_redacted=redact(body.content),
    )
    db.add(user_msg)
    await db.flush()

    # Build context
    llm_messages = _build_messages_for_llm(conv.messages + [user_msg])

    # Call LLM via SDK
    client = LLMClient(provider=provider, model=model)
    result = await client.chat(conv_id, llm_messages)

    # Save assistant message
    assistant_msg = Message(
        conversation_id=conv_id,
        role=MessageRole.assistant,
        content=result["content"],
        content_redacted=redact(result["content"]),
        token_count=result["usage"].get("completion_tokens"),
    )
    db.add(assistant_msg)

    # Update conversation title from first user message
    if conv.title == "New conversation" and len(conv.messages) == 0:
        conv.title = body.content[:60] + ("…" if len(body.content) > 60 else "")

    await db.flush()
    await db.refresh(assistant_msg)

    return MessageOut(
        id=assistant_msg.id,
        conversation_id=assistant_msg.conversation_id,
        role=assistant_msg.role,
        content=assistant_msg.content,
        token_count=assistant_msg.token_count,
        created_at=assistant_msg.created_at,
    )


@router.post("/{conv_id}/messages/stream")
async def send_message_stream(
    conv_id: uuid.UUID,
    body: MessageCreate,
    db: AsyncSession = Depends(get_db),
):
    """Streaming chat turn — returns Server-Sent Events."""
    conv = await _get_conversation_or_404(conv_id, db)
    if conv.status == ConversationStatus.cancelled:
        raise HTTPException(status_code=400, detail="Conversation is cancelled. Resume it first.")

    provider = body.provider or conv.provider
    model = body.model or conv.model

    # Save user message
    user_msg = Message(
        conversation_id=conv_id,
        role=MessageRole.user,
        content=body.content,
        content_redacted=redact(body.content),
    )
    db.add(user_msg)
    await db.flush()

    llm_messages = _build_messages_for_llm(conv.messages + [user_msg])

    client = LLMClient(provider=provider, model=model)
    full_response_parts = []

    async def event_generator():
        nonlocal full_response_parts
        async for chunk in client.chat_stream(conv_id, llm_messages):
            full_response_parts.append(chunk)
            yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"

        # Persist assistant message after stream ends using a fresh session
        from app.db.base import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            full_text = "".join(full_response_parts)
            assistant_msg = Message(
                conversation_id=conv_id,
                role=MessageRole.assistant,
                content=full_text,
                content_redacted=redact(full_text),
            )
            session.add(assistant_msg)
            # Update title if still default
            from sqlalchemy import select as _select
            result = await session.execute(_select(Conversation).where(Conversation.id == conv_id))
            c = result.scalar_one_or_none()
            if c and c.title == "New conversation":
                c.title = body.content[:60] + ("…" if len(body.content) > 60 else "")
            await session.commit()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
