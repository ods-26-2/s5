from collections import Counter

from src.domain.entities.heatmap_grid import HeatmapGrid
from src.domain.exceptions import InvalidHeatmapGridError
from src.domain.value_objects.spatial_cell import SpatialCell
from src.domain.value_objects.world_coordinate import WorldCoordinate


class GridDensityCalculator:
    """Bucketiza pontos de mundo em uma grade regular e calcula a densidade (0.0-1.0) de cada célula."""

    def __init__(self, cell_size: float) -> None:
        if cell_size <= 0:
            raise InvalidHeatmapGridError("cell_size deve ser maior que zero.")
        self._cell_size = cell_size

    def calculate(self, points: list[WorldCoordinate], grid_id: str) -> HeatmapGrid:
        if not points:
            return HeatmapGrid(grid_id=grid_id, cells=())

        bucket_counts = Counter(self._bucket_for(point) for point in points)
        peak_count = max(bucket_counts.values())

        cells = tuple(
            SpatialCell(
                position=WorldCoordinate(
                    x=col * self._cell_size,
                    y=row * self._cell_size,
                ),
                density=count / peak_count,
            )
            for (row, col), count in sorted(bucket_counts.items())
        )
        return HeatmapGrid(grid_id=grid_id, cells=cells)

    def _bucket_for(self, point: WorldCoordinate) -> tuple[int, int]:
        return (int(point.y // self._cell_size), int(point.x // self._cell_size))
