from datetime import datetime, timedelta

from src.domain.services.aggregation_strategy import DwellTimeAggregationStrategy
from src.domain.entities.normalized_event import NormalizedEvent
from src.domain.value_objects.time_window import TimeWindow
from src.domain.value_objects.world_coordinate import WorldCoordinate

ORIGIN = WorldCoordinate(x=0.0, y=0.0)


def _event(event_type: str, timestamp: datetime) -> NormalizedEvent:
    return NormalizedEvent(event_type=event_type, origin="camera-01", coords=ORIGIN, timestamp=timestamp)


def test_deve_calcular_dwell_time_medio_quando_houver_pares_enter_exit():
    base_time = datetime(2026, 9, 10, 10, 0, 0)
    events = [
        _event("enter", base_time),
        _event("exit", base_time + timedelta(seconds=10)),
        _event("enter", base_time + timedelta(seconds=20)),
        _event("exit", base_time + timedelta(seconds=40)),
    ]
    window = TimeWindow(start_time=base_time, end_time=base_time + timedelta(minutes=1))

    metric = DwellTimeAggregationStrategy().aggregate(events, zone_id="zone-01", window=window)

    assert metric.dwell_time_avg == 15.0
    assert metric.total_count == 2


def test_deve_retornar_dwell_time_zero_quando_nao_houver_pares_completos():
    base_time = datetime(2026, 9, 10, 10, 0, 0)
    events = [_event("enter", base_time)]
    window = TimeWindow(start_time=base_time, end_time=base_time + timedelta(minutes=1))

    metric = DwellTimeAggregationStrategy().aggregate(events, zone_id="zone-01", window=window)

    assert metric.dwell_time_avg == 0.0
    assert metric.total_count == 1


def test_deve_calcular_pico_de_ocupacao_quando_houver_sobreposicao():
    base_time = datetime(2026, 9, 10, 10, 0, 0)
    events = [
        _event("enter", base_time),
        _event("enter", base_time + timedelta(seconds=5)),
        _event("exit", base_time + timedelta(seconds=10)),
        _event("enter", base_time + timedelta(seconds=15)),
        _event("exit", base_time + timedelta(seconds=20)),
        _event("exit", base_time + timedelta(seconds=25)),
    ]
    window = TimeWindow(start_time=base_time, end_time=base_time + timedelta(minutes=1))

    metric = DwellTimeAggregationStrategy().aggregate(events, zone_id="zone-01", window=window)

    assert metric.occupancy_peak == 2
