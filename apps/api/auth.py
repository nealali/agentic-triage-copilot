"""
Minimal API-key authentication (optional).

Why this exists
---------------
In real enterprise workflows, you must know "who did what":
- who created a decision
- who ingested guidance
- who accessed exports

This module provides a lightweight auth layer that is:
- easy to understand (good for learning)
- easy to run locally (just environment variables)
- optional (default OFF so the MVP remains frictionless)

This is NOT intended to be a complete security solution.
In production you would typically use:
- SSO (OIDC/SAML)
- JWT validation
- a proper identity/role system
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from fastapi import Header, HTTPException


@dataclass(frozen=True)
class AuthContext:
    """Identity + roles derived from the API key."""

    user: str
    roles: set[str]
    authenticated: bool


def _is_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def auth_enabled() -> bool:
    """
    Feature flag for auth.

    Default: disabled (MVP-friendly).
    Enable with: AUTH_ENABLED=1
    """

    return _is_truthy(os.getenv("AUTH_ENABLED"))


def parse_api_keys(raw: str | None) -> dict[str, AuthContext]:
    """
    Parse API_KEYS from env into a mapping.

    Format (comma-separated entries):
        API_KEYS="key:user:role1|role2,otherkey:svc:admin"

    Examples:
        API_KEYS="devkey:jdoe:reviewer"
        API_KEYS="devkey:jdoe:reviewer|writer,adminkey:admin:admin"
    """

    if not raw:
        return {}

    mapping: dict[str, AuthContext] = {}
    entries = [e.strip() for e in raw.split(",") if e.strip()]
    for entry in entries:
        parts = entry.split(":")
        if len(parts) != 3:
            raise ValueError(
                "Invalid API_KEYS entry. Expected 'key:user:role1|role2' (comma-separated)."
            )
        key, user, roles_raw = parts
        roles = {r.strip() for r in roles_raw.split("|") if r.strip()}
        mapping[key] = AuthContext(user=user, roles=roles, authenticated=True)
    return mapping


def get_auth_context(x_api_key: str | None) -> AuthContext:
    """
    Resolve the request's AuthContext.

    Behavior:
    - if auth is disabled: returns a non-authenticated SYSTEM context
    - if enabled: requires X-API-Key and validates it against API_KEYS
    """

    if not auth_enabled():
        return AuthContext(user="SYSTEM", roles={"system"}, authenticated=False)

    api_keys = parse_api_keys(os.getenv("API_KEYS"))
    if not api_keys:
        raise HTTPException(
            status_code=500,
            detail="AUTH_ENABLED=1 but API_KEYS is not configured",
        )

    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key")

    ctx = api_keys.get(x_api_key)
    if ctx is None:
        raise HTTPException(status_code=401, detail="Invalid X-API-Key")
    return ctx


def require_roles(required: set[str] | None = None):
    """
    FastAPI dependency factory for role-based access control.

    If auth is disabled, this dependency allows the request (MVP mode).
    If auth is enabled, it enforces:
    - valid X-API-Key
    - role membership (if required is provided)
    """

    def _dep(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> AuthContext:
        ctx = get_auth_context(x_api_key)

        if auth_enabled() and required:
            if ctx.roles.isdisjoint(required):
                raise HTTPException(status_code=403, detail="Forbidden (insufficient role)")
        return ctx

    return _dep
