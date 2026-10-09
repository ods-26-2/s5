from abc import ABC, abstractmethod

from src.domain.entities.normalized_event import NormalizedEvent
from src.domain.entities.occupancy_metric import OccupancyMetric
from src.domain.value_objects.time_window import TimeWindow

ENTER_EVENT_TYPE = "enter"
EXIT_EVENT_TYPE = "exit"


class AggregationStrategy(ABC):
    """Converte um conjunto de eventos normalizados de uma zona em uma métrica acumulada."""

    @abstractmethod
    def aggregate(
        self, events: list[NormalizedEvent], zone_id: str, window: TimeWindow
    ) -> OccupancyMetric: ...


class DwellTimeAggregationStrategy(AggregationStrategy):
    """Pareia eventos enter/exit em ordem cronológica para calcular tempo de
    permanência médio, pico de ocupação simultânea e contagem total de entradas."""

    def aggregate(
        self, events: list[NormalizedEvent], zone_id: str, window: TimeWindow
    ) -> OccupancyMetric:
        entries = sorted(
            (e for e in events if e.event_type == ENTER_EVENT_TYPE), key=lambda e: e.timestamp
        )
        exits = sorted(
            (e for e in events if e.event_type == EXIT_EVENT_TYPE), key=lambda e: e.timestamp
        )

        return OccupancyMetric(
            zone_id=zone_id,
            window=window,
            dwell_time_avg=self._average_dwell_time(entries, exits),
            occupancy_peak=self._peak_concurrency(entries, exits),
            total_count=len(entries),
        )

    @staticmethod
    def _average_dwell_time(
        entries: list[NormalizedEvent], exits: list[NormalizedEvent]
    ) -> float:
        pairs = list(zip(entries, exits))
        if not pairs:
            return 0.0
        durations = [(exit_.timestamp - enter.timestamp).total_seconds() for enter, exit_ in pairs]
        return sum(durations) / len(durations)

    @staticmethod
    def _peak_concurrency(entries: list[NormalizedEvent], exits: list[NormalizedEvent]) -> int:
        timeline = [(e.timestamp, 1) for e in entries] + [(e.timestamp, -1) for e in exits]
        timeline.sort(key=lambda item: item[0])

        current = 0
        peak = 0
        for _, delta in timeline:
            current += delta
            peak = max(peak, current)
        return peak
