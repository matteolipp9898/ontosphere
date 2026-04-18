"""WebSocket endpoint for real-time ontology processing events via Redis pub/sub."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(tags=["events"])


@router.websocket("/ontologies/{ontology_id}/events")
async def ontology_events(websocket: WebSocket, ontology_id: uuid.UUID) -> None:
    """Subscribe to real-time processing events for an ontology.

    Connects to a Redis pub/sub channel named ``ontology:<id>:events`` and
    forwards every published message to the WebSocket client as JSON.
    """
    await websocket.accept()
    channel_name = f"ontology:{ontology_id}:progress"
    logger.info("WebSocket client connected for channel %s.", channel_name)

    # Late import so the module can be loaded even if redis is not installed
    # (e.g. during unit tests with mocked dependencies).
    try:
        import redis.asyncio as aioredis
    except ImportError:
        logger.error("redis.asyncio is not available; closing WebSocket.")
        await websocket.close(code=1011, reason="Redis client unavailable.")
        return

    redis_client: aioredis.Redis | None = None
    pubsub: aioredis.client.PubSub | None = None

    try:
        redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(channel_name)

        async def _reader() -> None:
            """Read messages from Redis pub/sub and send to the WebSocket."""
            assert pubsub is not None  # for type checker
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                data = message["data"]
                # Try to parse as JSON; forward raw string otherwise.
                try:
                    payload = json.loads(data) if isinstance(data, str) else data
                except (json.JSONDecodeError, TypeError):
                    payload = {"message": str(data)}
                await websocket.send_json(payload)

        async def _ping() -> None:
            """Periodically ping the WebSocket to detect stale connections."""
            while True:
                await asyncio.sleep(30)
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break

        # Run the reader and ping tasks concurrently; cancel both when either
        # finishes (e.g. client disconnects).
        reader_task = asyncio.create_task(_reader())
        ping_task = asyncio.create_task(_ping())

        try:
            done, pending = await asyncio.wait(
                {reader_task, ping_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
        except WebSocketDisconnect:
            reader_task.cancel()
            ping_task.cancel()

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected from channel %s.", channel_name)
    except Exception:
        logger.exception("Error in WebSocket handler for channel %s.", channel_name)
        try:
            await websocket.close(code=1011, reason="Internal server error.")
        except Exception:
            pass
    finally:
        if pubsub is not None:
            try:
                await pubsub.unsubscribe(channel_name)
                await pubsub.close()
            except Exception:
                logger.debug("Error closing pubsub for channel %s.", channel_name)
        if redis_client is not None:
            try:
                await redis_client.close()
            except Exception:
                logger.debug("Error closing redis client for channel %s.", channel_name)
        logger.info("WebSocket handler ended for channel %s.", channel_name)
