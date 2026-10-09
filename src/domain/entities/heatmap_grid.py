from dataclasses import dataclass

from src.domain.exceptions import InvalidHeatmapGridError
from src.domain.value_objects.spatial_cell import SpatialCell


@dataclass(frozen=True)
class HeatmapGrid:
    """Grade 2D de densidade espacial do mapa de calor."""

    grid_id: str
    cells: tuple[SpatialCell, ...]

    def __post_init__(self) -> None:
        if not self.grid_id.strip():
            raise InvalidHeatmapGridError("grid_id não pode ser vazio.")
