"""Timezone utilities.

Single source of truth for all timezone operations.
All datetime display, formatting, and conversion should use these functions.

Display settings (time_format, show_timezone) are read from user configuration.
"""

from datetime import UTC, datetime

from teamarr.config import (
    get_show_timezone,
    get_time_format,
    get_user_timezone,
    get_user_timezone_str,
)

__all__ = [
    "get_user_timezone",
    "get_user_timezone_str",
    "now_user",
    "now_utc",
    "to_user_tz",
    "to_utc",
    "format_time",
    "format_date",
    "format_date_short",
    "format_datetime_xmltv",
    "get_timezone_abbrev",
]


def now_user() -> datetime:
    """Get current time in user timezone."""
    return datetime.now(get_user_timezone())


def now_utc() -> datetime:
    """Get current time in UTC."""
    return datetime.now(UTC)


def to_user_tz(dt: datetime) -> datetime:
    """Convert any datetime to user timezone.

    Args:
        dt: Datetime to convert (must be timezone-aware)

    Returns:
        Datetime in user timezone
    """
    if dt.tzinfo is None:
        raise ValueError("Cannot convert naive datetime - must be timezone-aware")
    return dt.astimezone(get_user_timezone())


def to_utc(dt: datetime) -> datetime:
    """Convert any datetime to UTC.

    Args:
        dt: Datetime to convert (must be timezone-aware)

    Returns:
        Datetime in UTC
    """
    if dt.tzinfo is None:
        raise ValueError("Cannot convert naive datetime - must be timezone-aware")
    return dt.astimezone(UTC)


def format_time(dt: datetime, include_tz: bool | None = None) -> str:
    """Format time for display using user's display settings.

    Uses user's configured time format (12h/24h) and show_timezone setting.

    Args:
        dt: Datetime to format (will be converted to user tz)
        include_tz: Override for timezone display (None = use user setting)

    Returns:
        Formatted time string (e.g., '7:30 PM EST' or '19:30')
    """
    local_dt = to_user_tz(dt)

    # Get user's time format preference
    time_format = get_time_format()

    if time_format == "24h":
        time_str = local_dt.strftime("%H:%M")
    else:
        # 12-hour format
        time_str = local_dt.strftime("%-I:%M %p")

    # Determine if we should show timezone
    show_tz = include_tz if include_tz is not None else get_show_timezone()

    if show_tz:
        tz_abbrev = get_timezone_abbrev(local_dt)
        return f"{time_str} {tz_abbrev}"
    return time_str


def format_date(dt: datetime) -> str:
    """Format date for display (e.g., 'December 14, 2025').

    Args:
        dt: Datetime to format (will be converted to user tz)

    Returns:
        Formatted date string
    """
    local_dt = to_user_tz(dt)
    return local_dt.strftime("%B %-d, %Y")


def format_date_short(dt: datetime) -> str:
    """Format short date for display (e.g., 'Dec 14').

    Args:
        dt: Datetime to format (will be converted to user tz)

    Returns:
        Formatted short date string
    """
    local_dt = to_user_tz(dt)
    return local_dt.strftime("%b %-d")


def format_datetime_xmltv(dt: datetime) -> str:
    """Format datetime for XMLTV output in user's configured timezone.

    Converts to user timezone and formats as: YYYYMMDDHHMMSS +/-HHMM

    Args:
        dt: Datetime to format (will be converted to user timezone)

    Returns:
        XMLTV formatted datetime string with timezone offset
    """
    local_dt = to_user_tz(dt)
    # Get UTC offset in seconds, convert to HHMM format
    offset = local_dt.utcoffset()
    if offset is None:
        offset_str = "+0000"
    else:
        total_seconds = int(offset.total_seconds())
        sign = "+" if total_seconds >= 0 else "-"
        total_seconds = abs(total_seconds)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        offset_str = f"{sign}{hours:02d}{minutes:02d}"
    return local_dt.strftime("%Y%m%d%H%M%S") + " " + offset_str


def get_timezone_abbrev(dt: datetime) -> str:
    """Get timezone abbreviation for a datetime.

    Args:
        dt: Datetime with timezone info

    Returns:
        Timezone abbreviation (e.g., 'EST', 'EDT', 'PST')
    """
    if dt.tzinfo is None:
        return ""
    return dt.strftime("%Z")
