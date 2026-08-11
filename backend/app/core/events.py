"""Event system.

A lightweight, in-process publish/subscribe event bus that decouples
components without requiring an external message broker.
"""

import asyncio
import logging
from collections import defaultdict
from typing import Any, Callable, Coroutine, Dict, List, Set, Union

logger = logging.getLogger(__name__)

# Type alias for event handlers
Handler = Callable[..., Union[None, Coroutine[Any, Any, None]]]

# ---------------------------------------------------------------------------
# Event bus
# ---------------------------------------------------------------------------


class EventBus:
    """Simple synchronous/asynchronous event bus."""

    def __init__(self):
        self._handlers: Dict[str, List[Handler]] = defaultdict(list)
        self._once_handlers: Dict[str, Set[Handler]] = defaultdict(set)

    # ---- Subscription ----

    def on(self, event: str, handler: Handler) -> None:
        """Register *handler* to be called every time *event* is emitted.

        Args:
            event: Event name (case-sensitive).
            handler: Callable; may be sync or async.
        """
        self._handlers[event].append(handler)
        logger.debug("Registered handler for event '%s': %s", event, handler)

    def once(self, event: str, handler: Handler) -> None:
        """Register *handler* to be called only once on the next *event*.

        After the first invocation the handler is automatically unregistered.
        """
        self._once_handlers[event].add(handler)

    def off(self, event: str, handler: Handler) -> None:
        """Unregister *handler* for *event*."""
        if event in self._handlers and handler in self._handlers[event]:
            self._handlers[event].remove(handler)
        if event in self._once_handlers:
            self._once_handlers[event].discard(handler)

    # ---- Emission ----

    def emit(self, event: str, *args, **kwargs) -> None:
        """Synchronously emit an event, calling all registered handlers.

        Async handlers are scheduled via ``asyncio.create_task``; sync
        handlers are called inline.  Errors in handlers are logged but
        never propagate.
        """
        all_handlers = list(self._handlers.get(event, []))
        once_handlers = self._once_handlers.pop(event, set())
        all_handlers.extend(once_handlers)

        for handler in all_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    try:
                        loop = asyncio.get_running_loop()
                        task = loop.create_task(handler(*args, **kwargs))

                        # 兜底：异步 handler 内部异常不丢失（否则 "Task exception was never retrieved"）
                        def _log_task_exception(t, _event=event, _handler=handler):
                            if t.cancelled():
                                return
                            exc = t.exception()
                            if exc:
                                logger.error(
                                    "异步事件处理器异常 event=%s handler=%s: %s",
                                    _event, getattr(_handler, "__name__", _handler), exc,
                                )
                        task.add_done_callback(_log_task_exception)
                    except RuntimeError:
                        asyncio.run(handler(*args, **kwargs))
                else:
                    handler(*args, **kwargs)
            except Exception:
                logger.exception(
                    "Error handling event '%s' with handler %s", event, handler
                )

    async def emit_async(self, event: str, *args, **kwargs) -> None:
        """Asynchronously emit an event, awaiting all handlers.

        Sync handlers are called via ``asyncio.to_thread``.
        """
        all_handlers = list(self._handlers.get(event, []))
        once_handlers = self._once_handlers.pop(event, set())
        all_handlers.extend(once_handlers)

        for handler in all_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(*args, **kwargs)
                else:
                    await asyncio.to_thread(handler, *args, **kwargs)
            except Exception:
                logger.exception(
                    "Error handling event '%s' with handler %s", event, handler
                )

    # ---- Introspection ----

    def listener_count(self, event: str) -> int:
        """Return the number of handlers registered for *event*."""
        return len(self._handlers.get(event, [])) + len(
            self._once_handlers.get(event, set())
        )

    def events(self) -> List[str]:
        """Return all event names that have registered handlers."""
        events = set(self._handlers.keys()) | set(self._once_handlers.keys())
        return sorted(events)

    def clear(self) -> None:
        """Remove all handlers for all events."""
        self._handlers.clear()
        self._once_handlers.clear()


# ---------------------------------------------------------------------------
# Global event bus instance
# ---------------------------------------------------------------------------

event_bus = EventBus()
