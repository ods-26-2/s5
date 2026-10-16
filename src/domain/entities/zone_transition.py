from dataclasses import dataclass
from datetime import datetime

from src.domain.exceptions import InvalidZoneTransitionError

ENTER = "ENTER"
EXIT = "EXIT"


@dataclass(frozen=True)
class ZoneTransition:
    """Entrada ou saída de um rastro em uma zona, já confirmada pela histerese de S1
    (ods.s1.zone_transition). occurred_at é o captured_at do envelope."""

    zone_id: str
    track_id: str
    object_class: str
    transition: str
    occurred_at: datetime
    entered_at: datetime
    source_id: str
    session_id: str
    dwell_s: int | None = None

    def __post_init__(self) -> None:
        for name in ("zone_id", "track_id", "object_class", "source_id", "session_id"):
            if not getattr(self, name).strip():
                raise InvalidZoneTransitionError(f"{name} não pode ser vazio.")
        if self.transition not in (ENTER, EXIT):
            raise InvalidZoneTransitionError(f"transition inválida: {self.transition!r}.")
        if self.transition == EXIT and self.dwell_s is None:
            raise InvalidZoneTransitionError("dwell_s é obrigatório em EXIT.")
        if self.dwell_s is not None and self.dwell_s < 0:
            raise InvalidZoneTransitionError("dwell_s não pode ser negativo.")
