from dataclasses import dataclass, field
from datetime import datetime

from src.domain.exceptions import InvalidZoneOccupancyError


@dataclass(frozen=True)
class ZoneOccupancySample:
    """Contagem de uma zona a partir de observed_at, publicada por S1 a cada mudança
    (ods.s1.zone_occupancy). A contagem vale até a próxima amostra da mesma zona."""

    zone_id: str
    observed_at: datetime
    count: int
    source_id: str
    session_id: str
    count_by_class: dict[str, int] = field(default_factory=dict, compare=False)
    max_occupancy: int | None = None

    def __post_init__(self) -> None:
        for name in ("zone_id", "source_id", "session_id"):
            if not getattr(self, name).strip():
                raise InvalidZoneOccupancyError(f"{name} não pode ser vazio.")
        if self.count < 0:
            raise InvalidZoneOccupancyError("count não pode ser negativo.")
        if any(value < 0 for value in self.count_by_class.values()):
            raise InvalidZoneOccupancyError("count_by_class não pode ter valores negativos.")
        if self.max_occupancy is not None and self.max_occupancy < 0:
            raise InvalidZoneOccupancyError("max_occupancy não pode ser negativo.")
