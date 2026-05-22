"""
Lightweight in-process event bus.
Decouples the ingestion API from the database write path.
In production this would be replaced by Kafka / Redis Streams.
"""
import asyncio
import logging
from typing import Any, Callable, Dict, List

logger = logging.getLogger(__name__)


class EventBus:
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=10_000)
        self._running = False

    def subscribe(self, event_type: str, handler: Callable):
        self._subscribers.setdefault(event_type, []).append(handler)

    async def publish(self, event_type: str, payload: Any):
        await self._queue.put({"type": event_type, "payload": payload})

    async def start(self):
        self._running = True
        asyncio.create_task(self._process())
        logger.info("EventBus started")

    async def stop(self):
        self._running = False

    async def _process(self):
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                handlers = self._subscribers.get(event["type"], [])
                for handler in handlers:
                    try:
                        await handler(event["payload"])
                    except Exception as exc:
                        logger.error(f"EventBus handler error [{event['type']}]: {exc}")
                self._queue.task_done()
            except asyncio.TimeoutError:
                continue
            except Exception as exc:
                logger.error(f"EventBus processing error: {exc}")


# Singleton
bus = EventBus()
