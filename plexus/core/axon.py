"""The axon: turns USD change notices into coalesced events."""

from dataclasses import dataclass
from pathlib import Path
import threading
import time
from typing import Callable, Optional

from pxr import Sdf, Tf, Usd


@dataclass(frozen=True)
class StageEvent:
    paths: frozenset[Sdf.Path]
    resynced: frozenset[Sdf.Path]
    t: float


class PlexusAxon:
    """An axon that observes a stage and coalesces events."""

    def __init__(self, stage, debounce_s: float = 0.05):
        self._stage = stage
        self._debounce_s = debounce_s
        self._callbacks = []
        self._queue = []
        self._dispatcher_thread = None
        self._stop_event = threading.Event()
        self._listener = None
        self._queue_lock = threading.RLock()

    def subscribe(self, callback: Callable[[StageEvent], None]) -> None:
        """Subscribe a callback to receive coalesced StageEvents."""
        self._callbacks.append(callback)

    def start(self) -> None:
        """Start the axon. Must be called before any changes are made to the stage."""
        if self._listener is not None:
            return  # Already started

        self._stop_event.clear()
        self._dispatcher_thread = threading.Thread(target=self._dispatcher, daemon=True)
        self._dispatcher_thread.start()

        # Register notice listener
        self._listener = Tf.Notice.Register(Usd.Notice.ObjectsChanged, self._on_notice, self._stage)

    def cool(self) -> None:
        """Stop the axon and drain any pending events."""
        if self._listener is None:
            return  # Not started

        self._stop_event.set()
        if self._dispatcher_thread:
            self._dispatcher_thread.join(timeout=5.0)
        self._listener.Revoke()
        self._listener = None

    def _on_notice(self, notice, sender) -> None:
        """Notice callback that enqueues events."""
        changed_paths = frozenset(notice.GetChangedInfoOnlyPaths())
        resynced_paths = frozenset(notice.GetResyncedPaths())
        if not changed_paths and not resynced_paths:
            return

        event = StageEvent(
            paths=changed_paths,
            resynced=resynced_paths,
            t=time.perf_counter()
        )

        with self._queue_lock:
            self._queue.append(event)

    def _dispatcher(self) -> None:
        """Dispatcher thread that coalesces events within the debounce window."""
        while not self._stop_event.is_set():
            # Wait for first event or timeout
            try:
                event = self._queue.pop(0)
            except IndexError:
                # Queue is empty, wait for next event with timeout
                time.sleep(self._debounce_s)
                continue

            # Collect all events in the debounce window
            collected_paths = set(event.paths)
            collected_resynced = set(event.resynced)
            t = event.t

            # Collect as many events as possible within the debounce window
            start_time = time.perf_counter()
            while (time.perf_counter() - start_time) < self._debounce_s:
                try:
                    next_event = self._queue.pop(0)
                    collected_paths.update(next_event.paths)
                    collected_resynced.update(next_event.resynced)
                    t = max(t, next_event.t)
                except IndexError:
                    # No more events in queue
                    break

            # Dispatch to subscribers
            coalesced_event = StageEvent(
                paths=frozenset(collected_paths),
                resynced=frozenset(collected_resynced),
                t=t
            )

            for callback in self._callbacks:
                try:
                    callback(coalesced_event)
                except Exception:
                    # Log the exception but don't stop dispatching
                    pass
