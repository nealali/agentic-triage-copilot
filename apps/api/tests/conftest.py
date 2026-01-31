"""
pytest configuration (fixtures).

Why this file exists
--------------------
pytest automatically discovers fixtures in a file named `conftest.py`.
We use it to share common test setup across all tests.

Key concept for this project:
-----------------------------
Our "database" is currently in-memory global variables (dicts/lists).
That means tests can accidentally affect each other unless we reset state.

To keep tests independent and reliable, we clear the in-memory store
before each test.
"""

import pytest

from apps.api.storage import reset_in_memory_store


@pytest.fixture(autouse=True)
def _reset_store_before_each_test() -> None:
    """Automatically reset in-memory storage before each test."""

    reset_in_memory_store()

