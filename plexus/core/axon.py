"""The axon: turns USD change notices into coalesced events."""

from dataclasses import dataclass
from pathlib import Path
import threading
import time
from queue import Queue
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
        self._queue = Queue()
        self._dispatcher_thread = None
        self._stop_event = threading.Event()
        self._listener = None
        self._pending = 0
        self._window_open = False

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

        self._queue.put(event)
        self._pending += 1

    def _dispatcher(self) -> None:
        """Dispatcher thread that coalesces events within the debounce window."""
        while not self._stop_event.is_set():
            try:
                # Wait for first event or timeout
                event = self._queue.get(timeout=0.1)
            except:
                # Timeout, continue loop
                continue

            # Collect all events in the debounce window
            collected_paths = set(event.paths)
            collected_resynced = set(event.resynced)
            t = event.t
            notices_drained = 1

            # Check if we are starting a new window
            self._window_open = True
            
            # Collect as many events as possible within the debounce window
            start_time = time.perf_counter()
            while (remaining := self._debounce_s - (time.perf_counter() - start_time)) > 0:
                try:
                    next_event = self._queue.get(timeout=remaining)
                    collected_paths.update(next_event.paths)
                    collected_resynced.update(next_event.resynced)
                    t = max(t, next_event.t)
                    notices_drained += 1
                except:
                    # Timeout, break loop
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
                    import traceback
                    traceback.print_exc()

            # Decrement pending count by number of notices drained
            self._pending -= notices_drained
            
            # Close window
            self._window_open = False

    def idle(self) -> bool:
        """True when no event is pending, no window is open and no action is running."""
        return self._pending == 0 and not self._window_open
