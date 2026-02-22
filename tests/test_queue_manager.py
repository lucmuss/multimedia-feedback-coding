# -*- coding: utf-8 -*-
"""Tests for background queue manager."""

from __future__ import annotations

import threading
import time

from screenreview.core.queue_manager import QueueManager


def test_add_task_to_queue() -> None:
    qm = QueueManager(max_workers=2)
    future = qm.add_task("screen1", [("step1", lambda: 1)])
    qm.wait_for_all()
    assert future.done()
    qm.shutdown()


def test_task_executes_in_background() -> None:
    qm = QueueManager(max_workers=1)
    done = threading.Event()

    def _slow():
        time.sleep(0.05)
        done.set()
        return "ok"

    qm.add_task("screen1", [("slow", _slow)])
    assert done.wait(0.5) is True
    qm.shutdown()


def test_gui_thread_not_blocked_during_task() -> None:
    qm = QueueManager(max_workers=1)

    def _slow():
        time.sleep(0.1)
        return "ok"

    start = time.perf_counter()
    qm.add_task("screen1", [("slow", _slow)])
    elapsed = time.perf_counter() - start
    assert elapsed < 0.05
    qm.wait_for_all()
    qm.shutdown()


def test_tasks_for_one_screen_run_sequentially() -> None:
    qm = QueueManager(max_workers=1)
    order: list[str] = []

    qm.add_task(
        "screen1",
        [
            ("a", lambda: order.append("a")),
            ("b", lambda: order.append("b")),
            ("c", lambda: order.append("c")),
        ],
    )
    qm.wait_for_all()
    assert order == ["a", "b", "c"]
    qm.shutdown()


def test_tasks_for_different_screens_run_parallel() -> None:
    qm = QueueManager(max_workers=2)
    barrier = threading.Barrier(2)
    started = []

    def _task(name: str):
        def _run():
            started.append(name)
            barrier.wait(timeout=1)
            time.sleep(0.05)
            return name

        return _run

    qm.add_task("screen1", [("a", _task("screen1"))])
    qm.add_task("screen2", [("a", _task("screen2"))])
    qm.wait_for_all()
    assert set(started) == {"screen1", "screen2"}
    assert qm.peak_active_workers() >= 2
    qm.shutdown()


def test_progress_callback_called_with_correct_values() -> None:
    qm = QueueManager(max_workers=1)
    events: list[tuple[str, int, int, str]] = []
    qm.progress_updated = lambda s, i, t, m: events.append((s, i, t, m))
    qm.add_task("screen1", [("a", lambda: 1), ("b", lambda: 2)])
    qm.wait_for_all()
    assert any(event[0] == "screen1" and event[2] == 2 for event in events)
    qm.shutdown()


def test_completion_callback_called_on_success() -> None:
    qm = QueueManager(max_workers=1)
    completed = []
    qm.task_completed = lambda screen, result: completed.append((screen, result))
    qm.add_task("screen1", [("a", lambda: {"ok": True})])
    qm.wait_for_all()
    assert completed and completed[0][0] == "screen1"
    qm.shutdown()


def test_error_callback_called_on_failure() -> None:
    qm = QueueManager(max_workers=1)
    errors = []

    def _boom():
        raise RuntimeError("boom")

    qm.task_failed = lambda screen, error: errors.append((screen, error))
    qm.add_task("screen1", [("a", _boom)])
    qm.wait_for_all()
    assert errors and "boom" in errors[0][1]
    qm.shutdown()


def test_error_does_not_crash_other_tasks() -> None:
    qm = QueueManager(max_workers=2)
    completed = []
    errors = []
    qm.task_completed = lambda screen, result: completed.append(screen)
    qm.task_failed = lambda screen, error: errors.append((screen, error))
    qm.add_task("bad", [("a", lambda: (_ for _ in ()).throw(RuntimeError("fail")))])
    qm.add_task("good", [("a", lambda: "ok")])
    qm.wait_for_all()
    assert any(item[0] == "bad" for item in errors)
    assert "good" in completed
    qm.shutdown()


def test_cancel_pending_tasks() -> None:
    qm = QueueManager(max_workers=1)
    gate = threading.Event()

    def _block():
        gate.wait(0.3)
        return "done"

    qm.add_task("screen1", [("a", _block)])
    qm.add_task("screen2", [("a", lambda: "second")])
    qm.add_task("screen3", [("a", lambda: "third")])
    time.sleep(0.02)
    cancelled = qm.cancel_pending_tasks()
    gate.set()
    qm.wait_for_all()
    assert cancelled >= 1
    qm.shutdown()


def test_queue_empty_after_all_complete() -> None:
    qm = QueueManager(max_workers=1)
    qm.add_task("screen1", [("a", lambda: 1)])
    qm.wait_for_all()
    assert qm.queue_empty() is True
    qm.shutdown()


def test_max_parallel_workers_respected() -> None:
    qm = QueueManager(max_workers=2)

    def _slow():
        time.sleep(0.05)
        return 1

    for i in range(6):
        qm.add_task(f"screen{i}", [("a", _slow)])
    qm.wait_for_all()
    assert qm.peak_active_workers() <= 2
    qm.shutdown()


def test_cost_callback_called() -> None:
    qm = QueueManager(max_workers=1)
    updates = []
    qm.cost_updated = lambda total, entry: updates.append((total, entry))
    qm.add_task("screen1", [("cost", lambda: {"cost_total": 0.1, "cost_entry": {"x": 1}})])
    qm.wait_for_all()
    assert updates == [(0.1, {"x": 1})]
    qm.shutdown()

