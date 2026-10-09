from datetime import datetime, timedelta

from src.application.use_cases.rollup_metrics_use_case import RollupMetricsUseCase
from src.domain.entities.occupancy_metric import OccupancyMetric
from src.domain.services.downsampling_service import DownsamplingService
from src.domain.value_objects.time_window import TimeWindow

from .fakes import FakeTimeSeriesRepository


def test_deve_consolidar_metricas_finas_e_persistir_na_granularidade_alvo():
    base_time = datetime(2026, 9, 10, 10, 0, 0)
    source_window = TimeWindow(start_time=base_time, end_time=base_time + timedelta(seconds=1))
    target_window = TimeWindow(start_time=base_time, end_time=base_time + timedelta(minutes=1))

    repository = FakeTimeSeriesRepository()
    repository.metrics_to_return = [
        OccupancyMetric(
            zone_id="zone-01", window=source_window, dwell_time_avg=10.0, occupancy_peak=3, total_count=5
        )
    ]
    use_case = RollupMetricsUseCase(DownsamplingService(), repository)

    dto = use_case.execute(
        zone_id="zone-01",
        source_granularity="1s",
        source_window=source_window,
        target_granularity="1m",
        target_window=target_window,
    )

    assert dto.total_count == 5
    assert repository.saved_metrics[0][1] == "1m"
