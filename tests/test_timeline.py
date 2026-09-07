from bulkinout.core.models import ClinicalCase, TimelineEvent
from bulkinout.core.timeline import append_timeline_event, sort_timeline


def event(observed_at: str | None) -> TimelineEvent:
    return TimelineEvent(field="labs.creatinine", value=100, observed_at=observed_at)


def test_timeline_sorts_iso_dates_and_keeps_unknown_dates_last():
    events = [event(None), event("2026-09-07T09:30:00Z"), event("2024-01-03")]

    assert [item.observed_at for item in sort_timeline(events)] == [
        "2024-01-03",
        "2026-09-07T09:30:00Z",
        None,
    ]


def test_timeline_retains_non_iso_dates_without_interpreting_them():
    events = [event("07/09/2026"), event("2026-09-07")]

    assert [item.observed_at for item in sort_timeline(events)] == [
        "2026-09-07",
        "07/09/2026",
    ]


def test_append_timeline_event_maintains_order():
    case = ClinicalCase(timeline=[event("2026-09-07")])

    append_timeline_event(case, event("2025-01-01"))

    assert [item.observed_at for item in case.timeline] == ["2025-01-01", "2026-09-07"]
