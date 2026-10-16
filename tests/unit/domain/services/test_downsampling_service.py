from datetime import datetime, timedelta

import pytest

from src.domain.services.downsampling_service import DownsamplingService
from src.domain.entities.occupancy_metric import OccupancyMetric
from src.domain.value_objects.time_window import TimeWindow
from src.domain.exceptions import InvalidOccupancyMetricError


def _metric(dwell_time_avg: float, occupancy_peak: int, total_count: int, start: datetime) -> OccupancyMetric:
    window = TimeWindow(start_time=start, end_time=start + timedelta(seconds=1))
    return OccupancyMetric(
        zone_id="zone-01",
        window=window,
        dwell_time_avg=dwell_time_avg,
        occupancy_peak=occupancy_peak,
        total_count=total_count,
    )


def test_deve_consolidar_metricas_com_media_ponderada_por_total_count():
    base_time = datetime(2026, 9, 10, 10, 0, 0)
    metrics = [
        _metric(dwell_time_avg=10.0, occupancy_peak=2, total_count=2, start=base_time),
        _metric(dwell_time_avg=20.0, occupancy_peak=5, total_count=8, start=base_time + timedelta(seconds=1)),
    ]
    target_window = TimeWindow(start_time=base_time, end_time=base_time + timedelta(minutes=1))

    consolidated = DownsamplingService().rollup(metrics, zone_id="zone-01", target_window=target_window)

    assert consolidated.total_count == 10
    assert consolidated.occupancy_peak == 5
    assert consolidated.dwell_time_avg == pytest.approx(18.0)


def test_deve_lancar_excecao_quando_lista_de_metricas_for_vazia():
    base_time = datetime(2026, 9, 10, 10, 0, 0)
    target_window = TimeWindow(start_time=base_time, end_time=base_time + timedelta(minutes=1))

    with pytest.raises(InvalidOccupancyMetricError):
        DownsamplingService().rollup([], zone_id="zone-01", target_window=target_window)


def test_deve_consolidar_ocupacao_media_ponderada_pela_duracao_das_janelas():
    base_time = datetime(2026, 9, 10, 10, 0, 0)
    short = OccupancyMetric(
        zone_id="zone-01",
        window=TimeWindow(start_time=base_time, end_time=base_time + timedelta(seconds=10)),
        dwell_time_avg=0.0, occupancy_peak=4, total_count=0, occupancy_avg=4.0,
    )
    long = OccupancyMetric(
        zone_id="zone-01",
        window=TimeWindow(start_time=base_time + timedelta(seconds=10), end_time=base_time + timedelta(seconds=40)),
        dwell_time_avg=0.0, occupancy_peak=1, total_count=0, occupancy_avg=0.0,
    )
    target_window = TimeWindow(start_time=base_time, end_time=base_time + timedelta(seconds=40))

    consolidated = DownsamplingService().rollup([short, long], zone_id="zone-01", target_window=target_window)

    assert consolidated.occupancy_avg == pytest.approx(1.0)
