from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from .config import settings


ARGENTINA_TZ = ZoneInfo(settings.APP_TIMEZONE)


def argentina_now() -> datetime:
    return datetime.now(ARGENTINA_TZ).replace(tzinfo=None)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
