from datetime import datetime, timedelta

import pytest

from src.domain.entities.occupancy_metric import OccupancyMetric
from src.domain.value_objects.time_window import TimeWindow
from src.domain.exceptions import InvalidOccupancyMetricError


def _window() -> TimeWindow:
    start = datetime(2026, 9, 10, 10, 0, 0)
    return TimeWindow(start_time=start, end_time=start + timedelta(minutes=1))


def test_deve_criar_metrica_quando_valores_forem_validos():
    metric = OccupancyMetric(
        zone_id="zone-01", window=_window(), dwell_time_avg=12.5, occupancy_peak=4, total_count=10
    )
    assert metric.zone_id == "zone-01"
    assert metric.total_count == 10


def test_deve_lancar_excecao_quando_zone_id_for_vazio():
    with pytest.raises(InvalidOccupancyMetricError):
        OccupancyMetric(
            zone_id="", window=_window(), dwell_time_avg=0.0, occupancy_peak=0, total_count=0
        )


def test_deve_lancar_excecao_quando_dwell_time_avg_for_negativo():
    with pytest.raises(InvalidOccupancyMetricError):
        OccupancyMetric(
            zone_id="zone-01", window=_window(), dwell_time_avg=-1.0, occupancy_peak=0, total_count=0
        )


def test_deve_lancar_excecao_quando_total_count_for_negativo():
    with pytest.raises(InvalidOccupancyMetricError):
        OccupancyMetric(
            zone_id="zone-01", window=_window(), dwell_time_avg=0.0, occupancy_peak=0, total_count=-1
        )
