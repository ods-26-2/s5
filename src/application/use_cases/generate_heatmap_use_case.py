from datetime import datetime

from src.application.dtos.heatmap_query_dto import HeatmapQueryDTO
from src.domain.repositories.i_time_series_repository import ITimeSeriesRepository
from src.domain.services.grid_density_calculator import GridDensityCalculator
from src.domain.services.spatial_coordinate_converter import SpatialCoordinateConverter
from src.domain.value_objects.homography_matrix import HomographyMatrix
from src.domain.value_objects.pixel_coordinate import PixelCoordinate


class GenerateHeatmapUseCase:
    """Converte pixels de câmera em coordenadas de mundo via homografia I3, calcula a
    densidade espacial em grade, persiste e retorna o resultado."""

    def __init__(
        self,
        converter: SpatialCoordinateConverter,
        calculator: GridDensityCalculator,
        repository: ITimeSeriesRepository,
    ) -> None:
        self._converter = converter
        self._calculator = calculator
        self._repository = repository

    def execute(
        self,
        pixels: list[PixelCoordinate],
        homography: HomographyMatrix,
        grid_id: str,
        timestamp: datetime,
    ) -> HeatmapQueryDTO:
        world_points = [self._converter.convert(pixel, homography) for pixel in pixels]
        grid = self._calculator.calculate(world_points, grid_id)
        self._repository.save_heatmap_grid(grid, timestamp)
        return HeatmapQueryDTO.from_entity(grid)
