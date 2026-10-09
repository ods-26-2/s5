from datetime import datetime, timedelta

from src.application.use_cases.rollup_metrics_use_case import RollupMetricsUseCase
from src.domain.entities.occupancy_metric import OccupancyMetric
from src.domain.services.downsampling_service import DownsamplingService
from src.domain.services.moving_window_generator import MovingWindowGenerator
from src.domain.value_objects.time_window import TimeWindow
from src.infrastructure.database.duckdb_time_series_repository import DuckDBTimeSeriesRepository
from src.infrastructure.workers.downsampling_rollup_worker import DownsamplingRollupWorker


def test_deve_consolidar_metricas_de_1s_em_1m_no_rollup():
    repository = DuckDBTimeSeriesRepository(":memory:")
    reference_time = datetime(2026, 9, 10, 10, 1, 0)

    for offset in range(3):
        start = reference_time - timedelta(seconds=10 * (offset + 1))
        window = TimeWindow(start_time=start, end_time=start + timedelta(seconds=1))
        repository.save_occupancy_metric(
            OccupancyMetric(
                zone_id="zone-01", window=window, dwell_time_avg=5.0, occupancy_peak=1, total_count=2
            ),
            granularity="1s",
        )

    worker = DownsamplingRollupWorker(
        RollupMetricsUseCase(DownsamplingService(), repository), MovingWindowGenerator()
    )
    worker.run(zone_id="zone-01", reference_time=reference_time)

    one_minute_window = TimeWindow(
        start_time=reference_time - timedelta(minutes=1), end_time=reference_time
    )
    rolled_up = repository.query_metrics("zone-01", one_minute_window, "1m")

    assert len(rolled_up) == 1
    assert rolled_up[0].total_count == 6
