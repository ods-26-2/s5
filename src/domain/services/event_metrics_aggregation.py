from collections import defaultdict

from src.domain.entities.event_metric import EventMetric
from src.domain.entities.qualified_event import ENDED, UNCERTAIN, QualifiedEvent
from src.domain.value_objects.time_window import TimeWindow

GroupKey = tuple[str, str | None, str | None]


class EventMetricsAggregation:
    """Consolida as publicações de ods.s2.event de uma janela [início, fim), uma métrica por
    (event_type, zone_id, classe) com ocorrência:

    - count: eventos distintos (event_id) cujo started_at cai na janela;
    - uncertain_count: desses, os que estavam UNCERTAIN na última publicação anterior ao
      fim da janela;
    - duration_avg_ms: média do duration_ms dos eventos ENDED na janela.
    """

    def aggregate(self, events: list[QualifiedEvent], window: TimeWindow) -> list[EventMetric]:
        known = [e for e in events if e.occurred_at < window.end_time]
        latest_by_id: dict[str, QualifiedEvent] = {}
        for event in sorted(known, key=lambda e: e.occurred_at):
            latest_by_id[event.event_id] = event

        started: dict[GroupKey, list[QualifiedEvent]] = defaultdict(list)
        for event in latest_by_id.values():
            if window.start_time <= event.started_at < window.end_time:
                started[_key(event)].append(event)

        ended_durations: dict[GroupKey, list[int]] = defaultdict(list)
        for event in known:
            if event.phase == ENDED and event.occurred_at >= window.start_time:
                ended_durations[_key(event)].append(event.duration_ms)

        metrics = []
        for key in sorted(started.keys() | ended_durations.keys(), key=_sort_key):
            event_type, zone_id, object_class = key
            durations = ended_durations.get(key, [])
            metrics.append(
                EventMetric(
                    event_type=event_type,
                    window=window,
                    count=len(started.get(key, [])),
                    uncertain_count=sum(1 for e in started.get(key, []) if e.status == UNCERTAIN),
                    zone_id=zone_id,
                    object_class=object_class,
                    duration_avg_ms=round(sum(durations) / len(durations)) if durations else None,
                )
            )
        return metrics


def _key(event: QualifiedEvent) -> GroupKey:
    return (event.event_type, event.zone_id, event.object_class)


def _sort_key(key: GroupKey) -> tuple[str, str, str]:
    return tuple(part or "" for part in key)
