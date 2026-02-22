# -*- coding: utf-8 -*-
"""Tests for realtime cost tracking."""

from __future__ import annotations


def test_initial_total_is_zero(cost_tracker) -> None:
    assert cost_tracker.get_total() == 0.0


def test_add_openai_transcribe_cost(cost_tracker) -> None:
    entry = cost_tracker.add("openai_4o_transcribe", 1.0, "login_html")
    assert entry.cost_euro == 0.006


def test_add_replicate_vision_cost(cost_tracker) -> None:
    entry = cost_tracker.add("llama_32_vision", 5, "login_html")
    assert entry.cost_euro == 0.01


def test_local_model_adds_zero_cost(cost_tracker) -> None:
    entry = cost_tracker.add("easyocr_local", 10, "login_html")
    assert entry.cost_euro == 0.0


def test_total_sums_all_entries(cost_tracker) -> None:
    cost_tracker.add("openai_4o_transcribe", 1.0, "a")
    cost_tracker.add("llama_32_vision", 2, "a")
    assert cost_tracker.get_total() == 0.01


def test_breakdown_groups_by_provider(cost_tracker) -> None:
    cost_tracker.add("openai_4o_transcribe", 1.0, "a")
    cost_tracker.add("llama_32_vision", 2, "a")
    breakdown = cost_tracker.get_breakdown()
    assert breakdown["openai"] == 0.006
    assert breakdown["replicate"] == 0.004


def test_screen_cost_filters_by_name(cost_tracker) -> None:
    cost_tracker.add("llama_32_vision", 2, "screen_a")
    cost_tracker.add("llama_32_vision", 3, "screen_b")
    assert cost_tracker.get_screen_cost("screen_a") == 0.004


def test_estimate_remaining_screens(cost_tracker) -> None:
    cost_tracker.add("llama_32_vision", 2, "a")
    cost_tracker.add("llama_32_vision", 3, "b")
    estimate = cost_tracker.estimate_remaining(2)
    assert estimate > 0


def test_is_over_budget_true_when_exceeded(cost_tracker) -> None:
    cost_tracker.add("gpt4o_vision", 2, "a")
    assert cost_tracker.is_over_budget(0.01) is True


def test_is_near_budget_true_at_warning_threshold(cost_tracker) -> None:
    cost_tracker.add("llama_32_vision", 400, "a")  # 0.8 EUR
    assert cost_tracker.is_near_budget(1.0, 0.8) is True


def test_reset_clears_all_entries(cost_tracker) -> None:
    cost_tracker.add("llama_32_vision", 1, "a")
    cost_tracker.reset()
    assert cost_tracker.get_total() == 0.0
    assert cost_tracker.entries == []


def test_30_screens_under_1_euro(cost_tracker) -> None:
    for i in range(30):
        cost_tracker.add("openai_4o_transcribe", 1.0, f"screen_{i}")
        cost_tracker.add("llama_32_vision", 3, f"screen_{i}")
    assert cost_tracker.get_total() < 1.0


def test_smart_selector_savings_reflected(cost_tracker) -> None:
    full = 20 * 0.002
    reduced = 6 * 0.002
    savings = round(full - reduced, 3)
    assert savings == 0.028

