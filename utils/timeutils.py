import datetime
import pytz
from config import TIMEZONE

_WEEKDAYS_AR = ["الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]


def now_local() -> datetime.datetime:
    """Current wall-clock time in the bot's configured timezone (Africa/Cairo),
    returned as a naive datetime so it can be mixed freely with the rest of the
    (timezone-naive) date strings used across the codebase.

    This matters a lot: if the process runs on a server set to UTC (Railway,
    most Docker hosts, etc.) then plain datetime.datetime.now() would be 2-3
    hours off from Cairo time, which breaks "is it night right now" logic and
    can silently shift events by a day.
    """
    tz = pytz.timezone(TIMEZONE)
    return datetime.datetime.now(tz).replace(tzinfo=None)


def arabic_weekday(dt: datetime.datetime) -> str:
    return _WEEKDAYS_AR[dt.weekday()]
