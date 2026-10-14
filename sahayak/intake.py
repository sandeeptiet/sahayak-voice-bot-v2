"""Pure intake rules. Authentication and persistence belong at service boundaries."""
from datetime import datetime, timezone
from enum import StrEnum


class Category(StrEnum):
    ACCOUNT_ACCESS = "account_access"
    NETWORK = "network"
    VPN = "vpn"
    MICROSOFT_365 = "microsoft_365"
    HARDWARE = "hardware"
    OTHER = "other"
    SOFTWARE = "software"


class Priority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


_BASE_PRIORITY = {
    Category.ACCOUNT_ACCESS: Priority.HIGH,
    Category.NETWORK: Priority.HIGH,
    Category.VPN: Priority.MEDIUM,
    Category.MICROSOFT_365: Priority.MEDIUM,
    Category.HARDWARE: Priority.MEDIUM,
    Category.OTHER: Priority.MEDIUM,
    Category.SOFTWARE: Priority.LOW,
}
_URGENCY_PHRASES = (
    "cannot work", "can't work", "locked out", "urgent", "critical", "down",
    "not working at all", "completely stuck",
)
_LEVELS = tuple(Priority)


def assign_priority(category: Category | str, description: str) -> Priority:
    """Apply the inherited English substring baseline; bump at most once.

    This deliberately preserves broad matches such as 'down' in 'download'.
    Multilingual triage and more precise matching require evaluated refinements.
    """
    base = _BASE_PRIORITY[Category(category)]
    urgent = any(phrase in description.casefold() for phrase in _URGENCY_PHRASES)
    return _LEVELS[min(_LEVELS.index(base) + int(urgent), len(_LEVELS) - 1)]


def validate_callback_time(requested: datetime, *, now: datetime) -> datetime:
    """Return a future UTC instant; reject ambiguous naive times.

    Natural-language parsing and Asia/Kolkata interpretation must happen before
    this boundary. The caller supplies a trusted clock, never a browser clock.
    """
    for value in (requested, now):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Callback and current time must include a timezone")
    requested_utc = requested.astimezone(timezone.utc)
    if requested_utc <= now.astimezone(timezone.utc):
        raise ValueError("Callback must be in the future")
    return requested_utc
