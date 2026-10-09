from src.application.dtos.occupancy_metric_dto import OccupancyMetricDTO
from src.domain.repositories.i_time_series_repository import ITimeSeriesRepository
from src.domain.services.downsampling_service import DownsamplingService
from src.domain.value_objects.time_window import TimeWindow


class RollupMetricsUseCase:
    """Consolida métricas de uma granularidade fina (ex.: 1s) em uma métrica de
    granularidade mais grossa (ex.: 1m), persistindo o resultado do rollup."""

    def __init__(
        self, downsampling_service: DownsamplingService, repository: ITimeSeriesRepository
    ) -> None:
        self._downsampling_service = downsampling_service
        self._repository = repository

    def execute(
        self,
        zone_id: str,
        source_granularity: str,
        source_window: TimeWindow,
        target_granularity: str,
        target_window: TimeWindow,
    ) -> OccupancyMetricDTO:
        fine_metrics = self._repository.query_metrics(zone_id, source_window, source_granularity)
        consolidated = self._downsampling_service.rollup(fine_metrics, zone_id, target_window)
        self._repository.save_occupancy_metric(consolidated, target_granularity)
        return OccupancyMetricDTO.from_entity(consolidated)
