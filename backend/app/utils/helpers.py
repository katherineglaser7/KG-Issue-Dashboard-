"""
Shared utility functions.

This module contains helper functions that are used across multiple modules.
Keep utilities small and focused - if a utility grows complex, consider
moving it to its own service.

Current utilities:
- (none yet - add as needed)

Guidelines for adding utilities:
- Functions should be pure (no side effects) when possible
- Document input/output types clearly
- Add unit tests for complex logic
"""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Get current UTC datetime."""
    return datetime.now(timezone.utc)


def format_iso_timestamp(dt: datetime) -> str:
    """Format datetime as ISO 8601 string."""
    return dt.isoformat()
