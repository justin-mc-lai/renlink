"""Compatibility alias for :mod:`render_obscura`.

The renderer lives in ``render_obscura.py`` (TASK-022); this module keeps the
short import used by the app and the frozen task ledger working.
"""

from .render_obscura import (  # noqa: F401
    DEFAULT_CDP,
    DEFAULT_WAIT_MS,
    RenderTimeout,
    RenderUnavailable,
    cdp_endpoint,
    enabled,
    obscura_alive,
    prewarm,
    prewarm_html,
    render_html,
    render_page,
    render_wait_ms,
    stats,
)

__all__ = [
    "DEFAULT_CDP",
    "DEFAULT_WAIT_MS",
    "RenderTimeout",
    "RenderUnavailable",
    "cdp_endpoint",
    "enabled",
    "obscura_alive",
    "prewarm",
    "prewarm_html",
    "render_html",
    "render_page",
    "render_wait_ms",
    "stats",
]
