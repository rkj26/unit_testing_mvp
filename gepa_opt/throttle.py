"""The run's shared event loop, and client-side rate limiting to survive a free-tier request cap.

GEPA drives this project synchronously — it calls `adapter.evaluate` as a plain function — while
every model call underneath is async. `run_sync` bridges the two on ONE loop for the whole run.
A fresh `asyncio.run` per call is what strands loop-bound resources on a closed loop: the writer's
Gemini HTTP client and, before this, the limiter's `asyncio.Lock`.

Gemini's free tier allows only a few requests per minute per model, and GEPA is call-hungry. Without
pacing, the concurrent authoring burst and the per-rollout writer calls trip a 429 on the first
batch. These wrappers space every model call to stay under a requests-per-minute ceiling; the writer
is paced asynchronously (it is called under asyncio.gather), the reflection LM synchronously (GEPA
calls it as a plain callable).

Set the RPM above the provider's real limit — e.g. once billing is enabled — to make the throttle a
no-op.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Coroutine, TypeVar

import litellm

DEFAULT_WRITER_RPM = 4.0
DEFAULT_REFLECTION_RPM = 2.0
REFLECTION_RETRIES = 6

T = TypeVar("T")

_loop: asyncio.AbstractEventLoop | None = None


def run_sync(coro: Coroutine[Any, Any, T]) -> T:
    """Run `coro` to completion on the run's single, long-lived event loop."""
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)
    return _loop.run_until_complete(coro)


class AsyncRateLimiter:
    """Spaces awaited acquisitions to at most `rpm` per minute across all callers.

    Slot reservation is synchronous, so the limiter holds no loop-bound state and stays correct if
    it is ever driven from more than one loop: a caller claims the next slot by advancing `_next`
    before it yields, then sleeps until that slot arrives. Two callers therefore reserve two
    distinct slots rather than racing across the await.
    """

    def __init__(self, rpm: float) -> None:
        self._interval = 60.0 / rpm if rpm > 0 else 0.0
        self._next = 0.0

    async def acquire(self) -> None:
        if self._interval <= 0:
            return
        now = time.monotonic()
        scheduled = max(now, self._next)
        self._next = scheduled + self._interval
        if scheduled > now:
            await asyncio.sleep(scheduled - now)


class RateLimitedWriter:
    """Wraps a TrustedModel so every `complete()` is paced under a shared RPM ceiling."""

    def __init__(self, inner: Any, rpm: float) -> None:
        self._inner = inner
        self._limiter = AsyncRateLimiter(rpm)

    @property
    def name(self) -> str:
        return self._inner.name

    async def complete(self, prompt: str, kind: str) -> str:
        await self._limiter.acquire()
        return await self._inner.complete(prompt, kind)


class LiteLLMReflection:
    """A paced, retrying reflection LM for GEPA, driven through litellm as a sync callable.

    GEPA builds the full reflection prompt and calls this with it; we complete it. litellm resolves
    `gemini/<model>` from GOOGLE_API_KEY, falling back to GEMINI_API_KEY, and honours the provider's
    Retry-After on 429.

    An empty completion raises rather than returning "": GEPA catches a raising reflection LM and
    skips the iteration, whereas an empty string would be adopted as a candidate prompt — a failure
    silently becoming a value, and the worst possible value at that.
    """

    def __init__(self, model: str, rpm: float, max_retries: int = REFLECTION_RETRIES) -> None:
        self._model = model
        self._interval = 60.0 / rpm if rpm > 0 else 0.0
        self._max_retries = max_retries
        self._next = 0.0

    def __call__(self, prompt: str) -> str:
        self._pace()
        response = litellm.completion(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            num_retries=self._max_retries,
        )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError(f"reflection model {self._model!r} returned an empty completion")
        return content

    def _pace(self) -> None:
        if self._interval <= 0:
            return
        now = time.monotonic()
        wait = self._next - now
        if wait > 0:
            time.sleep(wait)
        self._next = max(now, self._next) + self._interval
