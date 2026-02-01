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

from apps.api import storage


@pytest.fixture(autouse=True)
def _reset_store_before_each_test() -> None:
    """
    Reset storage state before each test.

    Why this matters:
    - Tests must be independent (no cross-test contamination).
    - Our storage layer is swappable (in-memory for MVP, Postgres for persistence).
    - Using BACKEND.reset() keeps the same test suite working for both backends.
    """

    storage.BACKEND.reset()
