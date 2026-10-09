import math
from dataclasses import dataclass

from src.domain.value_objects.world_coordinate import WorldCoordinate
from src.domain.exceptions import InvalidSpatialCellError


@dataclass(frozen=True)
class SpatialCell:
    """Célula da grade do mapa de calor: uma posição no mundo e sua densidade."""

    position: WorldCoordinate
    density: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.density) or self.density < 0:
            raise InvalidSpatialCellError(
                f"Densidade da célula deve ser um número finito e não negativo, recebido {self.density}."
            )