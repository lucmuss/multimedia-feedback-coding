# -*- coding: utf-8 -*-
"""Tests for screen navigator behavior."""

from __future__ import annotations

from pathlib import Path

import pytest

from screenreview.core.navigator import Navigator
from screenreview.models.screen_item import ScreenItem


def _screen(index: int) -> ScreenItem:
    return ScreenItem(
        name=f"page_{index}",
        route=f"/page-{index}.html",
        viewport="mobile",
        viewport_size={"w": 390, "h": 844},
        timestamp_utc="2026-02-21T21:43:57Z",
        git_branch="main",
        git_commit=f"commit{index}",
        browser="chromium",
        screenshot_path=Path(f"/tmp/screenshot_{index}.png"),
        transcript_path=Path(f"/tmp/transcript_{index}.md"),
        metadata_path=Path(f"/tmp/meta_{index}.json"),
        extraction_dir=Path(f"/tmp/extraction_{index}"),
    )


@pytest.fixture
def screens() -> list[ScreenItem]:
    return [_screen(0), _screen(1), _screen(2)]


def test_starts_at_index_zero(screens: list[ScreenItem]) -> None:
    nav = Navigator(screens)
    assert nav.current_index() == 0


def test_current_returns_first_screen(screens: list[ScreenItem]) -> None:
    nav = Navigator(screens)
    assert nav.current() == screens[0]


def test_next_increments_index(screens: list[ScreenItem]) -> None:
    nav = Navigator(screens)
    nav.next()
    assert nav.current_index() == 1


def test_next_returns_new_current_screen(screens: list[ScreenItem]) -> None:
    nav = Navigator(screens)
    current = nav.next()
    assert current == screens[1]


def test_next_triggers_queue_for_previous_screen(screens: list[ScreenItem]) -> None:
    queued: list[ScreenItem] = []
    nav = Navigator(screens, enqueue_callback=queued.append)
    nav.next()
    assert queued == [screens[0]]
    assert screens[0].status == "processing"


def test_skip_increments_index(screens: list[ScreenItem]) -> None:
    nav = Navigator(screens)
    nav.skip()
    assert nav.current_index() == 1


def test_skip_does_not_trigger_queue(screens: list[ScreenItem]) -> None:
    queued: list[ScreenItem] = []
    nav = Navigator(screens, enqueue_callback=queued.append)
    nav.skip()
    assert queued == []


def test_skip_marks_screen_as_skipped(screens: list[ScreenItem]) -> None:
    nav = Navigator(screens)
    nav.skip()
    assert screens[0].status == "skipped"


def test_previous_decrements_index(screens: list[ScreenItem]) -> None:
    nav = Navigator(screens)
    nav.next()
    nav.previous()
    assert nav.current_index() == 0


def test_previous_does_not_go_below_zero(screens: list[ScreenItem]) -> None:
    nav = Navigator(screens)
    nav.previous()
    assert nav.current_index() == 0


def test_go_to_jumps_to_correct_index(screens: list[ScreenItem]) -> None:
    nav = Navigator(screens)
    selected = nav.go_to(2)
    assert selected == screens[2]
    assert nav.current_index() == 2


def test_go_to_invalid_index_raises_error(screens: list[ScreenItem]) -> None:
    nav = Navigator(screens)
    with pytest.raises(IndexError):
        nav.go_to(9)


def test_is_first_true_at_zero(screens: list[ScreenItem]) -> None:
    assert Navigator(screens).is_first() is True


def test_is_last_true_at_end(screens: list[ScreenItem]) -> None:
    nav = Navigator(screens)
    nav.go_to(2)
    assert nav.is_last() is True


def test_total_count_matches_screens(screens: list[ScreenItem]) -> None:
    assert Navigator(screens).total_count() == 3


def test_current_index_updates_correctly(screens: list[ScreenItem]) -> None:
    nav = Navigator(screens)
    nav.next()
    nav.next()
    assert nav.current_index() == 2


def test_next_at_last_screen_stays_at_last(screens: list[ScreenItem]) -> None:
    nav = Navigator(screens)
    nav.go_to(2)
    result = nav.next()
    assert nav.current_index() == 2
    assert result == screens[2]


def test_empty_navigator_raises_on_current() -> None:
    nav = Navigator([])
    with pytest.raises(IndexError):
        nav.current()
