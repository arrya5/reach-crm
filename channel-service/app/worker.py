"""Async worker pool that drains the send queue and fires callbacks.

Two distinct concurrency controls, modelling the two real bottlenecks:

* **Intake queue + worker pool** — workers rapidly drain the send queue and
  spawn each communication's lifecycle as its own task. The bounded queue is
  the backpressure point (a full queue blocks producers). At scale this queue
  becomes SQS/Kafka and workers a consumer group; the shape is unchanged.
* **Outbound callback semaphore** — the genuinely constrained resource is HTTP
  connections back to the CRM, so concurrent callbacks are capped by a
  semaphore rather than by holding a worker hostage for a message's whole
  (multi-second) lifecycle. Intake therefore stays fast even under load.

We also deliberately (a) dispatch each event on an independent jittered timer so
callbacks arrive **out of order**, and (b) inject occasional **duplicates** —
both to exercise the CRM's idempotent, order-independent ingestion. Callbacks
retry with exponential backoff so a transiently-down CRM doesn't lose events.
"""
from __future__ import annotations

import asyncio
import json
import random

import httpx

from .config import settings
from .security import sign
from .simulator import build_events

# Lightweight in-memory counters surfaced via /stats for the demo.
STATS = {"queued": 0, "processed": 0, "callbacks_sent": 0,
         "callbacks_failed": 0, "duplicates_injected": 0}

_queue: asyncio.Queue | None = None
_workers: list[asyncio.Task] = []
_lifecycles: set[asyncio.Task] = set()      # in-flight lifecycle tasks
_client: httpx.AsyncClient | None = None
_callback_sem: asyncio.Semaphore | None = None


def get_queue() -> asyncio.Queue:
    global _queue
    if _queue is None:
        _queue = asyncio.Queue(maxsize=settings.queue_maxsize)
    return _queue


async def enqueue(communication: dict, channel: str, callback_url: str) -> None:
    await get_queue().put({"comm": communication, "channel": channel, "callback_url": callback_url})
    STATS["queued"] += 1


def start_workers() -> None:
    global _client, _callback_sem
    _client = httpx.AsyncClient(timeout=15)
    _callback_sem = asyncio.Semaphore(settings.max_concurrent_callbacks)
    for _ in range(settings.worker_count):
        _workers.append(asyncio.create_task(_worker_loop()))


async def stop_workers() -> None:
    for w in _workers:
        w.cancel()
    _workers.clear()
    for t in list(_lifecycles):
        t.cancel()
    _lifecycles.clear()
    if _client is not None:
        await _client.aclose()


async def _worker_loop() -> None:
    """Drain the intake queue; hand each item to a concurrent lifecycle task."""
    queue = get_queue()
    while True:
        item = await queue.get()
        try:
            task = asyncio.create_task(_run_lifecycle(item))
            _lifecycles.add(task)
            task.add_done_callback(_lifecycles.discard)
            STATS["processed"] += 1
        finally:
            queue.task_done()


async def _run_lifecycle(item: dict) -> None:
    """Simulate one communication's delivery + engagement, posting callbacks."""
    try:
        events = build_events(item["comm"]["id"], item["channel"])
        await asyncio.gather(
            *(_dispatch_event(item["callback_url"], ev) for ev in events),
            return_exceptions=True,
        )
    except asyncio.CancelledError:
        raise
    except Exception:  # one bad message must not affect others
        pass


async def _dispatch_event(callback_url: str, event: dict) -> None:
    # Sleep this event's lifecycle delay (compressed) plus jitter that can
    # reorder adjacent events relative to their "true" timeline.
    delay = max(0.0, event["delay"]) * settings.speed + random.uniform(0, 0.4)
    await asyncio.sleep(delay)

    payload = {k: v for k, v in event.items() if k != "delay"}
    await _post_with_retry(callback_url, payload)

    # ~5% of events are re-sent (same event_id) to exercise CRM dedupe.
    if random.random() < 0.05:
        STATS["duplicates_injected"] += 1
        await asyncio.sleep(random.uniform(0.1, 0.5))
        await _post_with_retry(callback_url, payload)


async def _post_with_retry(url: str, payload: dict) -> None:
    raw = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json", "X-Signature": sign(raw, settings.webhook_secret)}
    assert _client is not None and _callback_sem is not None
    async with _callback_sem:                       # bound concurrent callbacks
        for attempt in range(settings.callback_max_retries):
            try:
                resp = await _client.post(url, content=raw, headers=headers)
                if resp.status_code < 300:
                    STATS["callbacks_sent"] += 1
                    return
            except httpx.HTTPError:
                pass
            await asyncio.sleep(settings.callback_backoff_base * (2 ** attempt))
    STATS["callbacks_failed"] += 1
