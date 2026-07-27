"""Resolve a model-returned relative date phrase (`due_raw`) into a concrete
`due_at` + `due_precision`, deterministically, anchored on the source's timestamp.

The LLM never returns a resolved date (plan.md §Phase 2). It hands us the raw phrase
("by Friday", "next week", "end of month") and we resolve it here so the logic is
inspectable and testable. Ambiguous phrases resolve to a representative instant and a
coarse precision; Phase 3 uses the precision to route vague deadlines to review.

Precision semantics:
  exact  - a specific date (and possibly time) was stated
  day    - resolves to a specific calendar day ("Friday", "tomorrow", "in 3 days")
  week   - resolves to a week-ish window ("next week", "end of week", "end of month")
  vague  - a deadline is implied but not resolvable ("a couple of days", unmatched)
  none   - no deadline at all
"""

import calendar
import re
from dataclasses import dataclass
from datetime import datetime, time, timedelta

from dateutil import parser as dateutil_parser
from dateutil.relativedelta import relativedelta

END_OF_DAY = time(23, 59, 59)

_WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


@dataclass(frozen=True)
class DueResolution:
    due_at: datetime | None
    precision: str  # exact | day | week | vague | none
    rule: str  # which branch fired, for explainability/tests


def _at_end_of_day(anchor: datetime, d) -> datetime:
    return datetime.combine(d, END_OF_DAY, tzinfo=anchor.tzinfo)


def _weekday_target(anchor: datetime, target_wd: int, is_next: bool) -> datetime:
    days_ahead = (target_wd - anchor.weekday()) % 7
    if is_next:
        days_ahead += 7  # push into the following week
    return _at_end_of_day(anchor, (anchor + timedelta(days=days_ahead)).date())


def _friday_of_week(anchor: datetime, weeks_ahead: int = 0) -> datetime:
    base = anchor + timedelta(weeks=weeks_ahead)
    days_ahead = (4 - base.weekday()) % 7  # 4 == Friday
    return _at_end_of_day(anchor, (base + timedelta(days=days_ahead)).date())


def _end_of_month(anchor: datetime, months_ahead: int = 0) -> datetime:
    base = anchor + relativedelta(months=months_ahead)
    last = calendar.monthrange(base.year, base.month)[1]
    return _at_end_of_day(anchor, base.replace(day=last).date())


def resolve_due(due_raw: str | None, anchor: datetime) -> DueResolution:
    if due_raw is None or not due_raw.strip():
        return DueResolution(None, "none", "empty")

    s = due_raw.strip().lower()
    # drop leading deadline prepositions so "by friday" == "friday"
    s = re.sub(r"^(by|before|due|on|no later than|until|till)\s+", "", s).strip()

    if s in {"today", "eod", "end of day", "by today"}:
        return DueResolution(_at_end_of_day(anchor, anchor.date()), "day", "today")
    if s in {"tomorrow", "tomorrow evening", "tomorrow morning", "tmrw"}:
        d = (anchor + timedelta(days=1)).date()
        return DueResolution(_at_end_of_day(anchor, d), "day", "tomorrow")
    if s in {"day after tomorrow", "the day after tomorrow"}:
        d = (anchor + timedelta(days=2)).date()
        return DueResolution(_at_end_of_day(anchor, d), "day", "day_after_tomorrow")

    # end of week
    if re.search(r"\b(end of (the )?week|eow)\b", s):
        return DueResolution(_friday_of_week(anchor), "week", "end_of_week")
    # end of month
    if re.search(r"\bend of (the )?month\b", s) or s == "eom":
        return DueResolution(_end_of_month(anchor), "week", "end_of_month")

    # next week (with an "early" nuance -> Monday, else Friday of next week)
    if "next week" in s:
        if "early" in s or "start of" in s or "beginning of" in s:
            monday = _weekday_target(anchor, 0, is_next=True)
            return DueResolution(monday, "week", "early_next_week")
        return DueResolution(_friday_of_week(anchor, weeks_ahead=1), "week", "next_week")
    if "this week" in s:
        return DueResolution(_friday_of_week(anchor), "week", "this_week")
    if "next month" in s:
        return DueResolution(_end_of_month(anchor, months_ahead=1), "week", "next_month")
    if re.search(r"\b(this month|later this month|sometime this month)\b", s):
        return DueResolution(_end_of_month(anchor), "vague", "this_month")

    # "a couple of days" / "a few days" — fuzzy counts
    if re.search(r"\b(a )?couple( of)? days?\b", s):
        d = (anchor + timedelta(days=2)).date()
        return DueResolution(_at_end_of_day(anchor, d), "vague", "couple_days")
    if re.search(r"\b(a )?few days?\b", s):
        d = (anchor + timedelta(days=3)).date()
        return DueResolution(_at_end_of_day(anchor, d), "vague", "few_days")

    # "in N day(s)/week(s)"
    m = re.search(r"\bin (\d+) days?\b", s)
    if m:
        d = (anchor + timedelta(days=int(m.group(1)))).date()
        return DueResolution(_at_end_of_day(anchor, d), "day", "in_n_days")
    m = re.search(r"\bin (\d+) weeks?\b", s)
    if m:
        d = (anchor + timedelta(weeks=int(m.group(1)))).date()
        return DueResolution(_at_end_of_day(anchor, d), "week", "in_n_weeks")

    # weekday name, optionally "next <weekday>"
    m = re.search(r"\b(next\s+)?(" + "|".join(_WEEKDAYS) + r")\b", s)
    if m:
        is_next = m.group(1) is not None
        target = _WEEKDAYS[m.group(2)]
        return DueResolution(
            _weekday_target(anchor, target, is_next), "day", "weekday"
        )

    # explicit calendar date fallback (only if it looks date-like)
    if re.search(r"\d", s) or re.search(
        r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)", s
    ):
        try:
            parsed = dateutil_parser.parse(
                s, default=anchor.replace(hour=23, minute=59, second=59), fuzzy=True
            )
            has_time = bool(re.search(r"\d\s*(am|pm)|\d:\d", s))
            return DueResolution(
                parsed, "exact" if has_time else "day", "explicit_date"
            )
        except (ValueError, OverflowError):
            pass

    # a deadline was implied but we couldn't resolve it -> route to review
    return DueResolution(None, "vague", "unresolved")
