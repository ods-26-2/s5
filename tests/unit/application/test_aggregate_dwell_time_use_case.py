from datetime import datetime, timedelta

from src.application.use_cases.aggregate_dwell_time_use_case import AggregateDwellTimeUseCase
from src.domain.entities.normalized_event import NormalizedEvent
from src.domain.services.aggregation_strategy import DwellTimeAggregationStrategy
from src.domain.services.moving_window_generator import MovingWindowGenerator
from src.domain.value_objects.world_coordinate import WorldCoordinate

from .fakes import FakeTimeSeriesRepository


def test_deve_persistir_e_retornar_uma_metrica_por_janela():
    reference_time = datetime(2026, 9, 10, 10, 0, 0)
    events = [
        NormalizedEvent(
            event_type="enter",
            origin="camera-01",
            coords=WorldCoordinate(x=0.0, y=0.0),
            timestamp=reference_time - timedelta(seconds=30),
        )
    ]
    repository = FakeTimeSeriesRepository()
    use_case = AggregateDwellTimeUseCase(
        DwellTimeAggregationStrategy(), MovingWindowGenerator(), repository
    )

    dtos = use_case.execute(events, zone_id="zone-01", reference_time=reference_time)

    assert len(dtos) == 3
    assert len(repository.saved_metrics) == 3
    assert repository.saved_metrics[0][1] == "1m"
    assert dtos[0].total_count == 1
