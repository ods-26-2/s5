from dataclasses import dataclass
from datetime import datetime

from src.domain.exceptions import InvalidNormalizedEventError
from src.domain.value_objects.world_coordinate import WorldCoordinate


@dataclass(frozen=True)
class NormalizedEvent:
    """Evento do Barramento B3 já normalizado para o domínio de S5."""

    event_type: str
    origin: str
    coords: WorldCoordinate
    timestamp: datetime

    def __post_init__(self) -> None:
        if not self.event_type.strip():
            raise InvalidNormalizedEventError("event_type não pode ser vazio.")
        if not self.origin.strip():
            raise InvalidNormalizedEventError("origin não pode ser vazio.")
