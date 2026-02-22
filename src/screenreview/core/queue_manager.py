# -*- coding: utf-8 -*-
"""Background task queue with sequential per-screen pipelines."""

from __future__ import annotations

import threading
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from typing import Any, Callable


TaskCallable = Callable[[], Any]
ProgressCallback = Callable[[str, int, int, str], None]
CompletionCallback = Callable[[str, Any], None]
ErrorCallback = Callable[[str, str], None]
CostCallback = Callable[[float, Any], None]


@dataclass
class QueueTask:
    """Sequential task chain for one screen."""

    screen_name: str
    steps: list[tuple[str, TaskCallable]]


class QueueManager:
    """Run one task chain per screen, parallel across screens."""

    def __init__(self, max_workers: int = 2) -> None:
        self.max_workers = int(max_workers)
        self._executor = ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix="screenreview")
        self._futures: list[Future] = []
        self._lock = threading.Lock()
        self._active = 0
        self._peak_active = 0
        self._cancelled = False
        self._queued_count = 0

        self.progress_updated: ProgressCallback | None = None
        self.task_completed: CompletionCallback | None = None
        self.task_failed: ErrorCallback | None = None
        self.cost_updated: CostCallback | None = None

    def add_task(
        self,
        screen_name: str,
        steps: list[tuple[str, TaskCallable]],
    ) -> Future:
        """Add a sequential task chain for one screen."""
        task = QueueTask(screen_name=screen_name, steps=steps)
        with self._lock:
            self._queued_count += 1
        future = self._executor.submit(self._run_task_chain, task)
        with self._lock:
            self._futures.append(future)
        return future

    def _run_task_chain(self, task: QueueTask) -> Any:
        with self._lock:
            self._active += 1
            self._peak_active = max(self._peak_active, self._active)
        try:
            last_result: Any = None
            total_steps = len(task.steps)
            for index, (step_name, func) in enumerate(task.steps, start=1):
                if self._cancelled:
                    raise RuntimeError("Queue cancelled")
                if self.progress_updated is not None:
                    self.progress_updated(task.screen_name, index - 1, total_steps, f"Starting {step_name}")
                last_result = func()
                if isinstance(last_result, dict) and "cost_total" in last_result and self.cost_updated is not None:
                    self.cost_updated(float(last_result["cost_total"]), last_result.get("cost_entry"))
                if self.progress_updated is not None:
                    self.progress_updated(task.screen_name, index, total_steps, f"Finished {step_name}")
            if self.task_completed is not None:
                self.task_completed(task.screen_name, last_result)
            return last_result
        except Exception as exc:
            if self.task_failed is not None:
                self.task_failed(task.screen_name, str(exc))
            raise
        finally:
            with self._lock:
                self._active = max(0, self._active - 1)
                self._queued_count = max(0, self._queued_count - 1)

    def cancel_pending_tasks(self) -> int:
        """Cancel futures that have not started yet."""
        self._cancelled = True
        cancelled = 0
        with self._lock:
            for future in self._futures:
                if future.cancel():
                    cancelled += 1
        return cancelled

    def wait_for_all(self, timeout: float | None = None) -> None:
        futures = self._snapshot_futures()
        if futures:
            wait(futures, timeout=timeout)

    def queue_empty(self) -> bool:
        with self._lock:
            return self._queued_count == 0

    def active_workers(self) -> int:
        with self._lock:
            return self._active

    def peak_active_workers(self) -> int:
        with self._lock:
            return self._peak_active

    def shutdown(self, wait_for_tasks: bool = True) -> None:
        self._executor.shutdown(wait=wait_for_tasks, cancel_futures=False)

    def _snapshot_futures(self) -> list[Future]:
        with self._lock:
            return list(self._futures)

