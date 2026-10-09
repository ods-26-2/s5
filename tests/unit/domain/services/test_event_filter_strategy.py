from datetime import datetime, timedelta

from src.domain.services.event_filter_strategy import DebounceHysteresisFilterStrategy
from src.domain.entities.normalized_event import NormalizedEvent
from src.domain.value_objects.world_coordinate import WorldCoordinate


def _event(origin: str, timestamp: datetime) -> NormalizedEvent:
    return NormalizedEvent(
        event_type="enter", origin=origin, coords=WorldCoordinate(x=0.0, y=0.0), timestamp=timestamp
    )


def test_deve_aceitar_primeiro_evento_de_uma_origin():
    strategy = DebounceHysteresisFilterStrategy(min_interval_seconds=5)
    assert strategy.should_accept(_event("camera-01", datetime(2026, 9, 10, 10, 0, 0))) is True


def test_deve_rejeitar_evento_repetido_dentro_do_intervalo_minimo():
    strategy = DebounceHysteresisFilterStrategy(min_interval_seconds=5)
    base_time = datetime(2026, 9, 10, 10, 0, 0)
    strategy.should_accept(_event("camera-01", base_time))

    accepted = strategy.should_accept(_event("camera-01", base_time + timedelta(seconds=2)))
    assert accepted is False


def test_deve_aceitar_evento_quando_intervalo_minimo_for_ultrapassado():
    strategy = DebounceHysteresisFilterStrategy(min_interval_seconds=5)
    base_time = datetime(2026, 9, 10, 10, 0, 0)
    strategy.should_accept(_event("camera-01", base_time))

    accepted = strategy.should_accept(_event("camera-01", base_time + timedelta(seconds=10)))
    assert accepted is True


def test_deve_tratar_origins_diferentes_de_forma_independente():
    strategy = DebounceHysteresisFilterStrategy(min_interval_seconds=5)
    base_time = datetime(2026, 9, 10, 10, 0, 0)
    strategy.should_accept(_event("camera-01", base_time))

    accepted = strategy.should_accept(_event("camera-02", base_time))
    assert accepted is True
