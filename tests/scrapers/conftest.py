"""Shared fixtures for scraper tests."""

from __future__ import annotations

import pytest

from aloha.scrapers.base import _circuit_breakers


@pytest.fixture(autouse=True)
def _clear_circuit_breakers() -> None:
    """Reset circuit breaker state before every test.

    Circuit breakers are stored in a module-level dict keyed by domain.
    Without clearing, failures in one test can trip a breaker that affects
    subsequent tests on the same domain.
    """
    _circuit_breakers.clear()
