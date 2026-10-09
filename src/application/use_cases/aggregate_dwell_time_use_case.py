from datetime import datetime

from src.application.dtos.occupancy_metric_dto import OccupancyMetricDTO
from src.domain.entities.normalized_event import NormalizedEvent
from src.domain.repositories.i_time_series_repository import ITimeSeriesRepository
from src.domain.services.aggregation_strategy import AggregationStrategy
from src.domain.services.moving_window_generator import MovingWindowGenerator

DEFAULT_WINDOW_SIZES_SECONDS = (60, 900, 3600)
GRANULARITY_LABELS = {60: "1m", 900: "15m", 3600: "1h"}


class AggregateDwellTimeUseCase:
    """Agrega eventos normalizados nas janelas móveis padrão (1m/15m/1h), persiste e
    retorna a métrica acumulada de cada janela."""

    def __init__(
        self,
        aggregation_strategy: AggregationStrategy,
        window_generator: MovingWindowGenerator,
        repository: ITimeSeriesRepository,
    ) -> None:
        self._aggregation_strategy = aggregation_strategy
        self._window_generator = window_generator
        self._repository = repository

    def execute(
        self,
        events: list[NormalizedEvent],
        zone_id: str,
        reference_time: datetime,
        window_sizes_seconds: tuple[int, ...] = DEFAULT_WINDOW_SIZES_SECONDS,
    ) -> list[OccupancyMetricDTO]:
        windows = self._window_generator.generate(reference_time, list(window_sizes_seconds))

        dtos = []
        for size_seconds, window in zip(window_sizes_seconds, windows):
            events_in_window = [
                event for event in events if window.start_time <= event.timestamp <= window.end_time
            ]
            metric = self._aggregation_strategy.aggregate(events_in_window, zone_id, window)
            granularity = GRANULARITY_LABELS.get(size_seconds, f"{size_seconds}s")
            self._repository.save_occupancy_metric(metric, granularity)
            dtos.append(OccupancyMetricDTO.from_entity(metric))

        return dtos
