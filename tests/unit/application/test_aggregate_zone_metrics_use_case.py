from datetime import datetime, timedelta

from src.application.use_cases.aggregate_zone_metrics_use_case import AggregateZoneMetricsUseCase
from src.domain.entities.zone_transition import ZoneTransition
from src.domain.services.aggregation_strategy import ZoneOccupancyAggregationStrategy
from src.domain.services.moving_window_generator import MovingWindowGenerator

from .fakes import FakeTimeSeriesRepository


def test_deve_persistir_e_retornar_uma_metrica_por_janela():
    reference_time = datetime(2026, 9, 10, 10, 0, 0)
    entered_at = reference_time - timedelta(seconds=30)
    transitions = [
        ZoneTransition(
            zone_id="zone-01",
            track_id="t-1",
            object_class="person",
            transition="ENTER",
            occurred_at=entered_at,
            entered_at=entered_at,
            source_id="cam0",
            session_id="s-1",
        )
    ]
    repository = FakeTimeSeriesRepository()
    use_case = AggregateZoneMetricsUseCase(
        ZoneOccupancyAggregationStrategy(), MovingWindowGenerator(), repository
    )

    dtos = use_case.execute(transitions, [], zone_id="zone-01", reference_time=reference_time)

    assert len(dtos) == 3
    assert len(repository.saved_metrics) == 3
    assert repository.saved_metrics[0][1] == "1m"
    assert dtos[0].total_count == 1
