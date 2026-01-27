from uuid import UUID

from agent.schemas.issue import Issue

# In-memory storage for issues. Resets on server restart.
ISSUES: dict[UUID, Issue] = {}
