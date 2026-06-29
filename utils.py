import re
from datetime import datetime, timedelta, date
import pytz

SGT = pytz.timezone("Asia/Singapore")


# ── Date helpers ──────────────────────────────────────────────────────────────

def now_sgt():
    return datetime.now(SGT)


def get_current_weekend_start() -> date:
    """Returns the Saturday of the current or next weekend."""
    today = now_sgt().date()
    weekday = today.weekday()  # Mon=0 … Sun=6
    if weekday == 5:
        return today
    if weekday == 6:
        return today - timedelta(days=1)
    return today + timedelta(days=5 - weekday)


def get_weekend_dates():
    sat = get_current_weekend_start()
    return sat, sat + timedelta(days=1)


def get_next_saturday() -> date:
    today = now_sgt().date()
    days_ahead = 5 - today.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return today + timedelta(days=days_ahead)


# ── Parsing ───────────────────────────────────────────────────────────────────

_WEEKDAYS = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thur": 3, "thurs": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}

_MONTHS = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


def _next_weekday(target: int) -> date:
    today = now_sgt().date()
    days_ahead = (target - today.weekday()) % 7 or 7
    return today + timedelta(days=days_ahead)


def parse_date(text: str):
    """Returns a date object or None.

    Accepts: today, tomorrow, Monday–Sunday (and abbreviations),
    DD/MM, DD/MM/YY, DD/MM/YYYY, '5 Jun', '5 June', 'June 5', '5th June'.
    """
    text = text.strip().lower()
    # strip ordinal suffixes: 1st 2nd 3rd 4th …
    text = re.sub(r"(\d+)(st|nd|rd|th)\b", r"\1", text)

    # today / tomorrow
    if text in ("today", "tdy"):
        return now_sgt().date()
    if text in ("tomorrow", "tmr", "tmrw"):
        return now_sgt().date() + timedelta(days=1)

    # weekday names
    if text in _WEEKDAYS:
        return _next_weekday(_WEEKDAYS[text])

    # numeric formats: DD/MM, DD/MM/YY, DD/MM/YYYY
    for pattern, fmt in [
        (r"\d{1,2}/\d{1,2}/\d{4}", "%d/%m/%Y"),
        (r"\d{1,2}/\d{1,2}/\d{2}",  "%d/%m/%y"),
    ]:
        if re.fullmatch(pattern, text):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                return None

    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})", text)
    if m:
        try:
            return date(now_sgt().year, int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None

    # "5 jun", "5 june", "june 5", "jun 5"
    m = re.fullmatch(r"(\d{1,2})\s+([a-z]+)", text)
    if not m:
        m = re.fullmatch(r"([a-z]+)\s+(\d{1,2})", text)
        if m:
            m = type("M", (), {"group": lambda self, i: [None, m.group(2), m.group(1)][i]})()
    if m:
        try:
            day   = int(m.group(1))
            month = _MONTHS.get(m.group(2))
            if month:
                return date(now_sgt().year, month, day)
        except ValueError:
            return None

    return None


def parse_time(text: str):
    """Returns (hour, minute) or None."""
    text = text.strip().lower().replace(" ", "")

    m = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?(am|pm)", text)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2) or 0)
        period = m.group(3)
        if period == "pm" and hour != 12:
            hour += 12
        elif period == "am" and hour == 12:
            hour = 0
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return hour, minute
        return None

    m = re.fullmatch(r"(\d{1,2}):(\d{2})", text)
    if m:
        hour, minute = int(m.group(1)), int(m.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return hour, minute

    return None


# ── Formatting ────────────────────────────────────────────────────────────────

def format_time(hour: int, minute: int) -> str:
    period = "am" if hour < 12 else "pm"
    h = hour % 12 or 12
    return f"{h}:{minute:02d}{period}" if minute else f"{h}{period}"


def format_date(date_str: str) -> str:
    """'2026-06-27' → 'Saturday, 27 Jun'"""
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return f"{d.strftime('%A')}, {d.day} {d.strftime('%b')}"


# ── Conflict detection ────────────────────────────────────────────────────────

def times_overlap(start1: str, end1: str, start2: str, end2: str, buffer_mins: int = 30) -> bool:
    """True if the two [start, end) ranges overlap after adding a buffer to each end."""
    def to_mins(t):
        h, m = map(int, t.split(":"))
        return h * 60 + m

    s1, e1 = to_mins(start1), to_mins(end1) + buffer_mins
    s2, e2 = to_mins(start2), to_mins(end2) + buffer_mins
    return not (e1 <= s2 or e2 <= s1)


# ── Username helpers ─────────────────────────────────────────────────────────

def normalize_username(username) -> str:
    """Lowercase and strip @ so comparisons against FAMILY keys always work."""
    return (username or "").lower().lstrip("@")


# ── Timezone-aware datetime ───────────────────────────────────────────────────

def get_event_datetime(date_str: str, time_str: str):
    dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    return SGT.localize(dt)
