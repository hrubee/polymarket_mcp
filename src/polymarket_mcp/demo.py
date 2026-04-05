"""DEMO mode guard — blocks write tools and returns clear error when DEMO_MODE=true."""

from __future__ import annotations

import json

from .auth import is_demo_mode

DEMO_ERROR = json.dumps(
    {
        "error": "DEMO_MODE",
        "message": "Trading disabled. Set DEMO_MODE=false and provide wallet credentials.",
    }
)


def require_live_mode() -> str | None:
    """Return DEMO_ERROR string if in demo mode, None otherwise."""
    if is_demo_mode():
        return DEMO_ERROR
    return None
