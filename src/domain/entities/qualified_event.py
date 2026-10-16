from dataclasses import dataclass
from datetime import datetime

from src.domain.exceptions import InvalidQualifiedEventError

CONFIRMED = "CONFIRMED"
UNCERTAIN = "UNCERTAIN"
STARTED = "STARTED"
UPDATED = "UPDATED"
ENDED = "ENDED"


@dataclass(frozen=True)
class QualifiedEvent:
    """Uma publicação de ods.s2.event. O mesmo event_id aparece em STARTED, UPDATED e
    ENDED; occurred_at é o captured_at do envelope de cada publicação."""

    event_id: str
    event_type: str
    status: str
    phase: str
    started_at: datetime
    duration_ms: int
    occurred_at: datetime
    session_id: str
    zone_id: str | None = None
    object_class: str | None = None

    def __post_init__(self) -> None:
        for name in ("event_id", "event_type", "session_id"):
            if not getattr(self, name).strip():
                raise InvalidQualifiedEventError(f"{name} não pode ser vazio.")
        if self.status not in (CONFIRMED, UNCERTAIN):
            raise InvalidQualifiedEventError(f"status inválido: {self.status!r}.")
        if self.phase not in (STARTED, UPDATED, ENDED):
            raise InvalidQualifiedEventError(f"phase inválida: {self.phase!r}.")
        if self.duration_ms < 0:
            raise InvalidQualifiedEventError("duration_ms não pode ser negativo.")
