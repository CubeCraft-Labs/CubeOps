"""USPS Tracking API v3 response parsing.

Kept free of Home Assistant imports so the pure parsing helpers stay
unit-testable without a full HA install.
"""

from __future__ import annotations

from typing import Any

from .const import ACCEPTANCE_KEYWORDS

_STATUS_MAX = 255
_STATUS_KEYS = ("status", "statusSummary", "statusCategory")
_EVENT_KEYS = ("eventType", "event", "eventCode")


def _tracking_status(payload: Any) -> str:
    """Reduce a USPS Tracking v3 response to a concise status string.

    Parses defensively across account/product schema variations: prefer a
    top-level summary field, else the most recent tracking event, else a
    short repr. Never returns a multi-thousand-char dump.
    """
    if isinstance(payload, dict):
        for key in _STATUS_KEYS:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()[:_STATUS_MAX]
        if event := _latest_event(payload.get("trackingEvents")):
            for key in _EVENT_KEYS:
                value = event.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()[:_STATUS_MAX]
    return repr(payload)[:_STATUS_MAX]


def _latest_event(events: Any) -> dict[str, Any] | None:
    """Return the tracking event with the newest ``eventTimestamp``."""
    valid = [event for event in events if isinstance(event, dict)] if isinstance(events, list) else []
    if not valid:
        return None
    return max(valid, key=lambda event: str(event.get("eventTimestamp", "")))


def _is_accepted(status: str) -> bool:
    """True when the concise status reads as USPS acceptance."""
    normalized = status.lower()
    return any(keyword in normalized for keyword in ACCEPTANCE_KEYWORDS)
