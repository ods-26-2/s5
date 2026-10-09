from datetime import datetime

from src.application.use_cases.generate_heatmap_use_case import GenerateHeatmapUseCase
from src.domain.services.grid_density_calculator import GridDensityCalculator
from src.domain.services.spatial_coordinate_converter import SpatialCoordinateConverter
from src.domain.value_objects.homography_matrix import HomographyMatrix
from src.domain.value_objects.pixel_coordinate import PixelCoordinate

from .fakes import FakeTimeSeriesRepository

IDENTITY = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def test_deve_gerar_e_persistir_heatmap_a_partir_de_pixels():
    repository = FakeTimeSeriesRepository()
    use_case = GenerateHeatmapUseCase(
        SpatialCoordinateConverter(), GridDensityCalculator(cell_size=1.0), repository
    )

    dto = use_case.execute(
        pixels=[PixelCoordinate(u=0.5, v=0.5), PixelCoordinate(u=0.6, v=0.6)],
        homography=HomographyMatrix(matrix=IDENTITY),
        grid_id="grid-01",
        timestamp=datetime(2026, 9, 10, 10, 0, 0),
    )

    assert dto.grid_id == "grid-01"
    assert len(dto.cells) == 1
    assert len(repository.saved_heatmaps) == 1
