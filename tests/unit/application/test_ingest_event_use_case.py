import pytest

from src.application.use_cases.ingest_event_use_case import IngestEventUseCase
from src.domain.services.event_filter_strategy import DebounceHysteresisFilterStrategy
from src.domain.exceptions import MalformedEventEnvelopeError

VALID_ENVELOPE = {
    "event_type": "enter",
    "origin": "camera-01",
    "coords": {"x": 1.0, "y": 2.0},
    "timestamp": "2026-09-10T10:00:00",
}


def test_deve_normalizar_evento_quando_envelope_for_valido():
    use_case = IngestEventUseCase(DebounceHysteresisFilterStrategy(min_interval_seconds=5))
    event = use_case.execute(VALID_ENVELOPE)
    assert event is not None
    assert event.event_type == "enter"
    assert event.origin == "camera-01"


def test_deve_retornar_none_quando_filtro_rejeitar_evento_repetido():
    use_case = IngestEventUseCase(DebounceHysteresisFilterStrategy(min_interval_seconds=5))
    use_case.execute(VALID_ENVELOPE)

    repeated = use_case.execute(VALID_ENVELOPE)
    assert repeated is None


def test_deve_lancar_excecao_quando_envelope_estiver_incompleto():
    use_case = IngestEventUseCase(DebounceHysteresisFilterStrategy(min_interval_seconds=5))
    with pytest.raises(MalformedEventEnvelopeError):
        use_case.execute({"event_type": "enter"})
