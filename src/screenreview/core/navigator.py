# -*- coding: utf-8 -*-
"""Navigation over screen items."""

from __future__ import annotations

from collections.abc import Callable

from screenreview.models.screen_item import ScreenItem


EnqueueCallback = Callable[[ScreenItem], None]


class Navigator:
    """Handle current position and movement across screens."""

    def __init__(
        self,
        screens: list[ScreenItem],
        enqueue_callback: EnqueueCallback | None = None,
    ) -> None:
        self._screens = screens
        self._index = 0
        self._enqueue_callback = enqueue_callback

    def current(self) -> ScreenItem:
        if not self._screens:
            raise IndexError("No screens available")
        return self._screens[self._index]

    def next(self) -> ScreenItem:
        if not self._screens:
            raise IndexError("No screens available")

        previous = self._screens[self._index]
        if self._index < len(self._screens) - 1:
            if previous.status not in {"skipped"} and self._enqueue_callback is not None:
                previous.status = "processing"
                self._enqueue_callback(previous)
            self._index += 1
        return self._screens[self._index]

    def skip(self) -> ScreenItem:
        if not self._screens:
            raise IndexError("No screens available")
        current = self._screens[self._index]
        current.status = "skipped"
        if self._index < len(self._screens) - 1:
            self._index += 1
        return self._screens[self._index]

    def previous(self) -> ScreenItem:
        if not self._screens:
            raise IndexError("No screens available")
        if self._index > 0:
            self._index -= 1
        return self._screens[self._index]

    def go_to(self, index: int) -> ScreenItem:
        if not self._screens:
            raise IndexError("No screens available")
        if index < 0 or index >= len(self._screens):
            raise IndexError(f"Invalid screen index: {index}")
        self._index = index
        return self._screens[self._index]

    def current_index(self) -> int:
        return self._index

    def total_count(self) -> int:
        return len(self._screens)

    def is_first(self) -> bool:
        return self._index == 0

    def is_last(self) -> bool:
        return self._index >= len(self._screens) - 1 if self._screens else True

