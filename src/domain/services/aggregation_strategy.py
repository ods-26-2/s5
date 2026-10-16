from abc import ABC, abstractmethod
from datetime import datetime

from src.domain.entities.occupancy_metric import OccupancyMetric
from src.domain.entities.zone_occupancy_sample import ZoneOccupancySample
from src.domain.entities.zone_transition import ENTER, EXIT, ZoneTransition
from src.domain.value_objects.time_window import TimeWindow


class AggregationStrategy(ABC):
    """Converte as transições e as amostras de ocupação de uma zona em uma métrica acumulada."""

    @abstractmethod
    def aggregate(
        self,
        transitions: list[ZoneTransition],
        samples: list[ZoneOccupancySample],
        zone_id: str,
        window: TimeWindow,
    ) -> OccupancyMetric: ...


class ZoneOccupancyAggregationStrategy(AggregationStrategy):
    """Agrega o que S1 já confirmou, sem refazer histerese nem pareamento:

    - total_count: transições ENTER na janela;
    - dwell_time_avg: média do dwell_s das transições EXIT na janela;
    - occupancy_peak: maior contagem vigente na janela;
    - occupancy_avg: contagem média ponderada pelo tempo em que cada amostra vigorou.

    A janela é semiaberta [start, end), para que janelas adjacentes não contem o mesmo
    instante duas vezes. A contagem vigente no início da janela é a da última amostra
    anterior a ela; sem amostra anterior, a zona é considerada vazia.
    """

    def aggregate(
        self,
        transitions: list[ZoneTransition],
        samples: list[ZoneOccupancySample],
        zone_id: str,
        window: TimeWindow,
    ) -> OccupancyMetric:
        in_window = [
            t for t in transitions if t.zone_id == zone_id and _contains(window, t.occurred_at)
        ]
        dwell_values = [t.dwell_s for t in in_window if t.transition == EXIT]
        zone_samples = sorted(
            (s for s in samples if s.zone_id == zone_id), key=lambda s: s.observed_at
        )
        steps = self._count_steps(zone_samples, window)

        return OccupancyMetric(
            zone_id=zone_id,
            window=window,
            dwell_time_avg=sum(dwell_values) / len(dwell_values) if dwell_values else 0.0,
            occupancy_peak=max(count for _, count in steps),
            total_count=sum(1 for t in in_window if t.transition == ENTER),
            occupancy_avg=self._time_weighted_average(steps, window),
        )

    @staticmethod
    def _count_steps(
        samples: list[ZoneOccupancySample], window: TimeWindow
    ) -> list[tuple[datetime, int]]:
        """Função degrau da contagem dentro da janela: (instante de início, contagem)."""
        initial_count = 0
        for sample in samples:
            if sample.observed_at < window.start_time:
                initial_count = sample.count
        steps = [(window.start_time, initial_count)]
        steps += [(s.observed_at, s.count) for s in samples if _contains(window, s.observed_at)]
        return steps

    @staticmethod
    def _time_weighted_average(steps: list[tuple[datetime, int]], window: TimeWindow) -> float:
        boundaries = [start for start, _ in steps[1:]] + [window.end_time]
        weighted_sum = sum(
            count * (end - start).total_seconds()
            for (start, count), end in zip(steps, boundaries)
        )
        return weighted_sum / window.duration_seconds


def _contains(window: TimeWindow, instant: datetime) -> bool:
    return window.start_time <= instant < window.end_time
