from dataclasses import dataclass

from src.domain.entities.heatmap_grid import HeatmapGrid


@dataclass(frozen=True)
class HeatmapQueryDTO:
    """Representação de transporte da grade de densidade espacial, para application/presentation."""

    grid_id: str
    cells: tuple[tuple[float, float, float], ...]

    @staticmethod
    def from_entity(grid: HeatmapGrid) -> "HeatmapQueryDTO":
        return HeatmapQueryDTO(
            grid_id=grid.grid_id,
            cells=tuple((cell.position.x, cell.position.y, cell.density) for cell in grid.cells),
        )
