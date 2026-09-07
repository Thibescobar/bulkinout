"""Small deterministic helpers for clinical timelines."""

from __future__ import annotations

from datetime import date, datetime, timezone

from ..models import ClinicalCase, TimelineEvent


def _sort_key(event: TimelineEvent) -> tuple[int, float, str]:
    """Sort ISO dates chronologically and retain stable order for unknown formats."""

    if not event.observed_at:
        return (2, 0.0, "")
    raw = event.observed_at.strip()
    try:
        if "T" not in raw and " " not in raw:
            parsed = datetime.combine(date.fromisoformat(raw), datetime.min.time(), timezone.utc)
        else:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
        return (0, parsed.timestamp(), raw)
    except ValueError:
        return (1, 0.0, raw)


def sort_timeline(events: list[TimelineEvent]) -> list[TimelineEvent]:
    """Return a stable chronological copy; undated events remain last."""

    return sorted(events, key=_sort_key)


def append_timeline_event(case: ClinicalCase, event: TimelineEvent) -> None:
    """Append an event and keep the case timeline chronological."""

    case.timeline.append(event)
    case.timeline = sort_timeline(case.timeline)
