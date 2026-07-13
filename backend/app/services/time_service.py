import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


DEFAULT_TIMEZONE = os.getenv("APP_TIMEZONE", "Europe/Paris")


def as_local_time(value, timezone_name: str = DEFAULT_TIMEZONE):
    if value is None:
        return None

    if not isinstance(value, datetime):
        return value

    # Existing SQLite dates are stored without tzinfo but were produced
    # with datetime.utcnow(), therefore they represent UTC.
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    try:
        target_timezone = ZoneInfo(timezone_name)
    except Exception:
        target_timezone = ZoneInfo("Europe/Paris")

    return value.astimezone(target_timezone)


def format_local_time(
    value,
    date_format: str = "%d/%m/%Y %H:%M:%S",
    timezone_name: str = DEFAULT_TIMEZONE,
):
    local_value = as_local_time(value, timezone_name)

    if local_value is None:
        return "-"

    if not isinstance(local_value, datetime):
        return str(local_value)

    return local_value.strftime(date_format)


def register_time_filters(templates):
    templates.env.filters["localtime"] = format_local_time
    return templates
