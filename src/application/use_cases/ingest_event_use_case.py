from datetime import datetime

from src.domain.entities.normalized_event import NormalizedEvent
from src.domain.exceptions import MalformedEventEnvelopeError
from src.domain.services.event_filter_strategy import EventFilterStrategy
from src.domain.value_objects.world_coordinate import WorldCoordinate


class IngestEventUseCase:
    """Consome um envelope bruto do Barramento B3 e produz um evento normalizado do domínio,
    aplicando debounce/histerese antes de aceitá-lo no fluxo."""

    def __init__(self, filter_strategy: EventFilterStrategy) -> None:
        self._filter_strategy = filter_strategy

    def execute(self, raw_envelope: dict) -> NormalizedEvent | None:
        event = self._parse(raw_envelope)
        if not self._filter_strategy.should_accept(event):
            return None
        return event

    @staticmethod
    def _parse(raw_envelope: dict) -> NormalizedEvent:
        try:
            coords = raw_envelope["coords"]
            return NormalizedEvent(
                event_type=raw_envelope["event_type"],
                origin=raw_envelope["origin"],
                coords=WorldCoordinate(x=coords["x"], y=coords["y"]),
                timestamp=datetime.fromisoformat(raw_envelope["timestamp"]),
            )
        except KeyError as error:
            raise MalformedEventEnvelopeError(
                f"Campo obrigatório ausente no envelope B1/B3: {error}"
            ) from error
