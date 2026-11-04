import math
from dataclasses import dataclass, field

from src.domain.exceptions import InvalidArtifactError

METERS = "METERS"
PIXELS = "PIXELS"


@dataclass(frozen=True)
class ZoneDefinition:
    """Uma zona nomeada do artefato ZONES (Especificação 1.0, seção 8)."""

    zone_id: str
    name: str
    polygon: tuple[tuple[float, float], ...]
    enter_hysteresis_ms: int
    exit_hysteresis_ms: int
    max_occupancy: int | None = None
    classes: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        if not self.zone_id.strip() or not self.name.strip():
            raise InvalidArtifactError("zone_id e name não podem ser vazios.")
        if len(self.polygon) < 3:
            raise InvalidArtifactError(f"Zona {self.zone_id}: o polígono precisa de pelo menos 3 pontos.")
        if any(len(point) != 2 or not all(math.isfinite(v) for v in point) for point in self.polygon):
            raise InvalidArtifactError(f"Zona {self.zone_id}: pontos do polígono devem ser [x, y] finitos.")
        if self.enter_hysteresis_ms < 0 or self.exit_hysteresis_ms < 0:
            raise InvalidArtifactError(f"Zona {self.zone_id}: histerese não pode ser negativa.")
        if self.max_occupancy is not None and self.max_occupancy < 0:
            raise InvalidArtifactError(f"Zona {self.zone_id}: max_occupancy não pode ser negativo.")


@dataclass(frozen=True)
class ZonesArtifact:
    """Conjunto de zonas de uma aplicação, numa versão. Em METERS as zonas estão no plano
    de space_id; em PIXELS, no quadro do único source_id."""

    artifact_id: str
    artifact_version: str
    coordinates: str
    source_ids: tuple[str, ...]
    zones: tuple[ZoneDefinition, ...]
    space_id: str | None = None
    owner: str | None = field(default=None, compare=False)

    def __post_init__(self) -> None:
        if not self.artifact_id.strip() or not self.artifact_version.strip():
            raise InvalidArtifactError("artifact_id e artifact_version não podem ser vazios.")
        if self.coordinates not in (METERS, PIXELS):
            raise InvalidArtifactError(f"coordinates inválido: {self.coordinates!r}.")
        if self.coordinates == METERS and not self.space_id:
            raise InvalidArtifactError("Zonas em METERS exigem space_id.")
        if self.coordinates == PIXELS and len(self.source_ids) != 1:
            raise InvalidArtifactError("Zonas em PIXELS exigem exatamente um source_id.")
        if not self.source_ids:
            raise InvalidArtifactError("source_ids não pode ser vazio.")
        zone_ids = [zone.zone_id for zone in self.zones]
        if len(zone_ids) != len(set(zone_ids)):
            raise InvalidArtifactError("zone_id repetido no artefato de zonas.")

    @property
    def single_source_id(self) -> str | None:
        """A câmera das zonas, quando o artefato tem uma só."""
        return self.source_ids[0] if len(self.source_ids) == 1 else None
