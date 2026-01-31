"""
Request correlation ID utilities.

What is a correlation ID?
------------------------
A correlation ID is a unique identifier attached to a request.
It helps you trace a single request through:
- API logs
- audit events
- downstream services (in a larger architecture)

Why it's valuable (enterprise signal)
-------------------------------------
When something goes wrong (or during inspections/reviews),
teams can search for one correlation ID and see:
"Everything that happened as part of this request."

Implementation approach
-----------------------
We use a `contextvars.ContextVar` to hold the correlation_id for the *current request*.
This is a production-friendly pattern because:
- route handlers don't need to pass correlation_id everywhere manually
- deeper layers (like storage helpers) can still access it safely
"""

from __future__ import annotations

from contextvars import ContextVar
from uuid import UUID

# The current request's correlation ID (if any).
_correlation_id_var: ContextVar[UUID | None] = ContextVar("correlation_id", default=None)


def set_correlation_id(correlation_id: UUID) -> None:
    """Set the correlation_id for the current request context."""

    _correlation_id_var.set(correlation_id)


def get_correlation_id() -> UUID | None:
    """Get the correlation_id for the current request context (or None)."""

    return _correlation_id_var.get()

