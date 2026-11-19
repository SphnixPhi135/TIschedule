"""Build an .ics calendar file with one person's upcoming presentations.

Standard library only, so it can be tested without Streamlit.

The schedule sheet stores dates without a year ("11-Jan"). Rows are in
chronological order, so the year is worked out from the order: the year
advances whenever the month goes backwards (December -> January), and the
starting year is the one that makes the schedule's span cover today (see
infer_dates). Assuming the current year instead would put a January-June
schedule in the past when viewed in December.

Events are all-day on the meeting date, because the meeting time is not
recorded anywhere. Set MEETING_START and MEETING_END to make them timed.
"""

import datetime as dt
import re

from mailer import SCHEDULE_URL

# Local meeting time, e.g. dt.time(9, 30) and dt.time(10, 30). None means
# all-day events.
MEETING_START = None
MEETING_END = None
TIMEZONE = "Europe/Amsterdam"

SLOTS = [
    ("Slot 1", "30-min presentation"),
    ("Slot 2", "5-min presentation"),
    ("Slot 3", "5-min presentation"),
    ("Slot 4", "5-min presentation"),
]

# Reminders, as offsets from the start of the event. For an all-day event
# the start is midnight, so -P2DT15H is the Friday before at 09:00.
ALARMS = [
    ("-P6DT15H", "TI meeting presentation in one week"),
    ("-P2DT15H", "TI meeting presentation on Monday"),
]


# A schedule still counts as the one running for this many days after its
# last meeting, so a finished schedule reads as past rather than next year.
_GRACE_DAYS = 30


def infer_dates(date_strings, today):
    """Turn the sheet's "D-Mon" strings into dates, in row order.

    The year of the first row is chosen so that the schedule's span
    (first to last meeting) covers today. If none does, the nearest
    upcoming span wins over a span that has already ended, unless the
    ended one is clearly closer. Picking the year closest to today for the
    first row alone would, late in a November-June schedule, move the whole
    schedule to the following year.

    Returns a list the same length as date_strings, with None for any
    entry that is not a date.
    """
    parsed = []
    for raw in date_strings:
        try:
            day_month = dt.datetime.strptime(str(raw).strip(), "%d-%b")
        except ValueError:
            parsed.append(None)
            continue
        parsed.append((day_month.month, day_month.day))

    if not any(parsed):
        return [None] * len(parsed)

    def dates_for(first_year):
        dates, year, prev_month = [], first_year, None
        for item in parsed:
            if item is None:
                dates.append(None)
                continue
            month, day = item
            if prev_month is not None and month < prev_month:
                year += 1
            prev_month = month
            dates.append(_safe_date(year, month, day))
        return dates

    def distance(dates):
        known = [d for d in dates if d is not None]
        start, end = known[0], known[-1] + dt.timedelta(days=_GRACE_DAYS)
        if start <= today <= end:
            return 0
        if today < start:
            return (start - today).days
        return 2 * (today - end).days   # prefer an upcoming schedule

    candidates = [dates_for(y) for y in (today.year - 1, today.year, today.year + 1)]
    return min(candidates, key=distance)


def _safe_date(year, month, day):
    # 29-Feb in a non-leap year would otherwise raise.
    try:
        return dt.date(year, month, day)
    except ValueError:
        return dt.date(year, month, 28)


def upcoming_talks(rows, person, today):
    """List (date, slot_label, other_presenters) for person, from today on.

    rows: dicts with "Date", "Slot 1".."Slot 4" and optionally "Notes".
    Cancelled meetings (Notes containing "cancel") are left out.
    """
    dates = infer_dates([r.get("Date", "") for r in rows], today)
    talks = []
    for row, date in zip(rows, dates):
        if date is None or date < today:
            continue
        if "cancel" in _clean(row.get("Notes")).lower():
            continue
        names = [_clean(row.get(slot)) for slot, _ in SLOTS]
        for (slot, label), name in zip(SLOTS, names):
            if name == person:
                others = [n for n in names if n and n != person]
                talks.append((date, label, others))
    return talks


def people_with_upcoming_talks(rows, today):
    """Everyone with at least one upcoming presentation, sorted."""
    dates = infer_dates([r.get("Date", "") for r in rows], today)
    people = set()
    for row, date in zip(rows, dates):
        if date is None or date < today or "cancel" in _clean(row.get("Notes")).lower():
            continue
        people.update(_clean(row.get(slot)) for slot, _ in SLOTS)
    people.discard("")
    return sorted(people)


def build_ics(person, talks, now=None):
    """Return the .ics file text for person's talks."""
    now = now or dt.datetime.now(dt.timezone.utc)
    stamp = now.astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//TI meeting schedule//Presentations//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escape(f'TI meeting - {person}')}",
    ]
    for date, label, others in talks:
        description = f"You give a {label} at the Tumor Immunology meeting."
        if others:
            description += f"\nAlso presenting: {', '.join(others)}."
        description += f"\nFull schedule: {SCHEDULE_URL}"
        lines += [
            "BEGIN:VEVENT",
            # Stable per person and date, so downloading again updates the
            # same event rather than adding a duplicate.
            f"UID:{date:%Y%m%d}-{_slug(person)}@ti-meeting-schedule",
            f"DTSTAMP:{stamp}",
        ]
        if MEETING_START and MEETING_END:
            lines += [
                f"DTSTART;TZID={TIMEZONE}:{date:%Y%m%d}T{MEETING_START:%H%M%S}",
                f"DTEND;TZID={TIMEZONE}:{date:%Y%m%d}T{MEETING_END:%H%M%S}",
            ]
        else:
            lines += [
                f"DTSTART;VALUE=DATE:{date:%Y%m%d}",
                f"DTEND;VALUE=DATE:{date + dt.timedelta(days=1):%Y%m%d}",
                "TRANSP:TRANSPARENT",
            ]
        lines += [
            f"SUMMARY:{_escape(f'TI meeting: your {label}')}",
            f"DESCRIPTION:{_escape(description)}",
            f"URL:{SCHEDULE_URL}",
        ]
        for trigger, text in ALARMS:
            lines += [
                "BEGIN:VALARM",
                "ACTION:DISPLAY",
                f"DESCRIPTION:{_escape(text)}",
                f"TRIGGER;RELATED=START:{trigger}",
                "END:VALARM",
            ]
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"


def _clean(value):
    text = "" if value is None else str(value).strip()
    return "" if text.lower() in ("nan", "none") else text


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "person"


def _escape(text):
    return (text.replace("\\", "\\\\").replace(";", "\\;")
                .replace(",", "\\,").replace("\n", "\\n"))


def _fold(line):
    """Fold to 75 octets per line, as RFC 5545 requires."""
    data = line.encode("utf-8")
    if len(data) <= 75:
        return line
    parts, start, limit = [], 0, 75
    while start < len(data):
        end = min(start + limit, len(data))
        # Don't split a multi-byte UTF-8 character.
        while end < len(data) and (data[end] & 0xC0) == 0x80:
            end -= 1
        parts.append(data[start:end].decode("utf-8"))
        start, limit = end, 74   # continuation lines start with a space
    return "\r\n ".join(parts)
