import math
from dataclasses import dataclass, field
from datetime import datetime

from src.domain.exceptions import InvalidPositionError


@dataclass(frozen=True)
class TrackPosition:
    """Um rastro em um quadro, como S1 o situa: em pixels e, quando a câmera tem calibração
    de I3, também em metros no plano de space_id. Uma entidade fundida de S2 pode vir só em
    metros, sem point_px."""

    track_id: str
    object_class: str
    point_px: tuple[float, float] | None
    zone_ids: tuple[str, ...] = field(default=())
    position_m: tuple[float, float] | None = None
    space_id: str | None = None

    def __post_init__(self) -> None:
        if not self.track_id.strip() or not self.object_class.strip():
            raise InvalidPositionError("track_id e class não podem ser vazios.")
        for name in ("point_px", "position_m"):
            value = getattr(self, name)
            if value is not None and (len(value) != 2 or not all(math.isfinite(v) for v in value)):
                raise InvalidPositionError(f"{name} deve ter dois valores finitos.")
        if (self.position_m is None) != (self.space_id is None):
            raise InvalidPositionError("position_m e space_id vêm sempre juntos.")
        if self.point_px is None and self.position_m is None:
            raise InvalidPositionError("A posição precisa de point_px ou de position_m.")


@dataclass(frozen=True)
class PositionSample:
    """Posições de um instante: as de uma câmera em um quadro (ods.s1.position) ou, com
    fused=True, as entidades fundidas entre câmeras (ods.s2.entity), em que track_id é o
    entity_id."""

    source_id: str
    session_id: str
    observed_at: datetime
    frame_index: int
    positions: tuple[TrackPosition, ...]
    fused: bool = False

    def __post_init__(self) -> None:
        if not self.source_id.strip() or not self.session_id.strip():
            raise InvalidPositionError("source_id e session_id não podem ser vazios.")
        if self.frame_index < 0:
            raise InvalidPositionError("frame_index não pode ser negativo.")
