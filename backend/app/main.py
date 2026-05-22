"""
Ollive LLM Platform — FastAPI Application Entry Point
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.core.config import settings
from app.db.base import engine, Base
from app.events.bus import bus
from app.api.routes import conversations, ingest, metrics, providers

# Import all models so SQLAlchemy registers them
from app.models import conversation as _models  # noqa

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ── Event bus handler ─────────────────────────────────────────────────────────

async def handle_inference_log(payload: dict):
    """Persist inference log from event bus to database."""
    from app.db.base import AsyncSessionLocal
    from app.models.conversation import InferenceLog, Conversation
    from sqlalchemy import select
    from app.core.pii import redact
    from datetime import datetime

    async with AsyncSessionLocal() as db:
        try:
            # Validate conversation exists
            result = await db.execute(
                select(Conversation).where(Conversation.id == payload["conversation_id"])
            )
            if not result.scalar_one_or_none():
                return

            def _parse_dt(v):
                if isinstance(v, str):
                    dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
                    # Strip timezone for PostgreSQL TIMESTAMP WITHOUT TIME ZONE
                    return dt.replace(tzinfo=None)
                if hasattr(v, 'tzinfo') and v.tzinfo is not None:
                    return v.replace(tzinfo=None)
                return v

            log = InferenceLog(
                conversation_id=payload["conversation_id"],
                provider=payload["provider"],
                model=payload["model"],
                started_at=_parse_dt(payload["started_at"]),
                ended_at=_parse_dt(payload["ended_at"]) if payload.get("ended_at") else None,
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
            await db.commit()
        except Exception as exc:
            logger.error(f"Failed to persist inference log: {exc}")
            await db.rollback()


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables ready")

    # Wire event bus
    bus.subscribe("inference_log", handle_inference_log)
    await bus.start()
    logger.info("Event bus started")

    yield

    # Shutdown
    await bus.stop()
    await engine.dispose()
    logger.info("Shutdown complete")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="LLM inference logging and ingestion platform",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ────────────────────────────────────────────────────────────────────

API_PREFIX = "/api/v1"

app.include_router(conversations.router, prefix=API_PREFIX)
app.include_router(ingest.router, prefix=API_PREFIX)
app.include_router(metrics.router, prefix=API_PREFIX)
app.include_router(providers.router, prefix=API_PREFIX)


@app.get("/health")
async def health():
    return {"status": "ok", "version": settings.APP_VERSION}


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }
