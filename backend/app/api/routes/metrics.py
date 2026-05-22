"""
Metrics / Dashboard API
=======================
Aggregated stats for the observability dashboard.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from typing import Optional, List
from datetime import datetime, timedelta

from app.db.base import get_db
from app.models.conversation import InferenceLog
from app.schemas.conversation import MetricsSummary, LatencyBucket, ProviderStats

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/summary", response_model=MetricsSummary)
async def get_summary(
    hours: int = Query(24, description="Look-back window in hours"),
    db: AsyncSession = Depends(get_db),
):
    since = datetime.utcnow() - timedelta(hours=hours)

    # Total count
    total_result = await db.execute(
        select(func.count(InferenceLog.id)).where(InferenceLog.created_at >= since)
    )
    total = total_result.scalar() or 0

    # Avg latency
    avg_result = await db.execute(
        select(func.avg(InferenceLog.latency_ms))
        .where(InferenceLog.created_at >= since, InferenceLog.latency_ms.isnot(None))
    )
    avg_latency = avg_result.scalar()

    # Total tokens
    tokens_result = await db.execute(
        select(func.sum(InferenceLog.total_tokens)).where(InferenceLog.created_at >= since)
    )
    total_tokens = tokens_result.scalar()

    # Per-provider breakdown
    provider_result = await db.execute(
        select(InferenceLog.provider, func.count(InferenceLog.id))
        .where(InferenceLog.created_at >= since)
        .group_by(InferenceLog.provider)
    )
    per_provider = {r[0]: r[1] for r in provider_result.all()}

    # Per-model breakdown
    model_result = await db.execute(
        select(InferenceLog.model, func.count(InferenceLog.id))
        .where(InferenceLog.created_at >= since)
        .group_by(InferenceLog.model)
    )
    per_model = {r[0]: r[1] for r in model_result.all()}

    # Error count
    error_result = await db.execute(
        select(func.count(InferenceLog.id))
        .where(InferenceLog.created_at >= since, InferenceLog.status == "error")
    )
    error_count = error_result.scalar() or 0
    success_count = total - error_count

    # P95 latency
    p95_result = await db.execute(
        select(InferenceLog.latency_ms)
        .where(InferenceLog.created_at >= since, InferenceLog.latency_ms.isnot(None))
        .order_by(InferenceLog.latency_ms)
    )
    latencies = [r[0] for r in p95_result.all()]
    p95 = None
    if latencies:
        idx = int(len(latencies) * 0.95)
        p95 = latencies[min(idx, len(latencies) - 1)]

    return MetricsSummary(
        total_requests=total,
        success_count=success_count,
        error_count=error_count,
        avg_latency_ms=round(avg_latency, 2) if avg_latency else None,
        p95_latency_ms=round(p95, 2) if p95 else None,
        total_tokens=total_tokens,
        requests_per_provider=per_provider,
        requests_per_model=per_model,
        error_rate=round(error_count / total, 4) if total > 0 else 0.0,
    )


@router.get("/latency-over-time", response_model=List[LatencyBucket])
async def get_latency_over_time(
    hours: int = Query(24),
    bucket_minutes: int = Query(30),
    db: AsyncSession = Depends(get_db),
):
    """Returns avg latency bucketed by time for charting."""
    since = datetime.utcnow() - timedelta(hours=hours)

    result = await db.execute(
        text("""
            SELECT
                date_trunc('hour', created_at) +
                    (EXTRACT(MINUTE FROM created_at)::int / :bucket * :bucket || ' minutes')::interval AS bucket,
                AVG(latency_ms) AS avg_latency,
                COUNT(*) AS req_count
            FROM inference_logs
            WHERE created_at >= :since AND latency_ms IS NOT NULL
            GROUP BY 1
            ORDER BY 1
        """),
        {"since": since, "bucket": bucket_minutes},
    )
    rows = result.all()
    return [
        LatencyBucket(
            timestamp=str(r[0]),
            avg_latency_ms=round(float(r[1]), 2),
            request_count=int(r[2]),
        )
        for r in rows
    ]


@router.get("/provider-stats", response_model=List[ProviderStats])
async def get_provider_stats(
    hours: int = Query(24),
    db: AsyncSession = Depends(get_db),
):
    since = datetime.utcnow() - timedelta(hours=hours)

    result = await db.execute(
        select(
            InferenceLog.provider,
            InferenceLog.model,
            func.count(InferenceLog.id).label("total"),
            func.avg(InferenceLog.latency_ms).label("avg_latency"),
            func.sum(InferenceLog.total_tokens).label("total_tokens"),
        )
        .where(InferenceLog.created_at >= since)
        .group_by(InferenceLog.provider, InferenceLog.model)
    )
    rows = result.all()

    stats = []
    for r in rows:
        # Get success count separately
        success_result = await db.execute(
            select(func.count(InferenceLog.id))
            .where(
                InferenceLog.created_at >= since,
                InferenceLog.provider == r.provider,
                InferenceLog.model == r.model,
                InferenceLog.status == "success",
            )
        )
        success_count = success_result.scalar() or 0
        stats.append(
            ProviderStats(
                provider=r.provider,
                model=r.model,
                total_requests=r.total,
                success_rate=round(success_count / r.total, 4) if r.total else 0,
                avg_latency_ms=round(float(r.avg_latency), 2) if r.avg_latency else 0,
                total_tokens=r.total_tokens or 0,
            )
        )
    return stats


@router.get("/recent-logs")
async def get_recent_logs(
    limit: int = Query(50, le=200),
    status: Optional[str] = Query(None),
    provider: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    q = select(InferenceLog).order_by(InferenceLog.created_at.desc()).limit(limit)
    if status:
        q = q.where(InferenceLog.status == status)
    if provider:
        q = q.where(InferenceLog.provider == provider)
    result = await db.execute(q)
    logs = result.scalars().all()
    return [
        {
            "id": str(l.id),
            "conversation_id": str(l.conversation_id),
            "provider": l.provider,
            "model": l.model,
            "latency_ms": l.latency_ms,
            "status": l.status,
            "total_tokens": l.total_tokens,
            "is_streaming": l.is_streaming,
            "created_at": l.created_at.isoformat(),
        }
        for l in logs
    ]
